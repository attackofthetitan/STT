import base64
import json
import unittest
import wave
from io import BytesIO
from unittest import mock

import numpy as np

import app


class FakeASR:
    def __init__(self, text="", language=None):
        self.text = text
        self.language = language

    def transcribe_audio_url(self, audio_url):
        return self.text, self.language


class AppHelpersTest(unittest.TestCase):
    def setUp(self):
        app.rate_limit_events.clear()

    def test_pcm16_wav_data_url(self):
        pcm = np.array([0, 1000, -1000], dtype="<i2").tobytes()

        data_url = app.pcm16_wav_data_url(pcm)

        prefix = "data:audio/wav;base64,"
        self.assertTrue(data_url.startswith(prefix))
        wav_bytes = base64.b64decode(data_url[len(prefix) :])
        with wave.open(BytesIO(wav_bytes), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), app.SAMPLE_RATE)
            self.assertEqual(wav.readframes(3), pcm)

    def test_empty_transcript_payload_shape(self):
        with mock.patch.object(app, "load_models"), mock.patch.object(app, "asr", FakeASR("")):
            payload = app.transcribe_pcm16(b"\0" * app.FRAME_SAMPLES * 2)

        self.assertEqual(payload["language"], "unknown")
        self.assertEqual(payload["transcript"], "")
        self.assertFalse(payload["ha_forwarded"])
        self.assertEqual(
            payload["raw"],
            {
                "type": "transcript",
                "domain": "unknown",
                "action": "none",
                "target": None,
                "state": None,
                "slots": {
                    "device": None,
                    "value": None,
                    "unit": None,
                    "mode": None,
                    "scene": None,
                },
                "raw_text": "",
                "raw_transcript": "",
            },
        )

    def test_home_assistant_forwarding_disabled_when_unset(self):
        parsed = {"type": "command", "action": "turn_on"}
        with mock.patch.object(app, "HA_WEBHOOK_URL", None), mock.patch("app.request.urlopen") as urlopen:
            self.assertFalse(app.forward_to_home_assistant(parsed))
        urlopen.assert_not_called()

    def test_home_assistant_forwarding_posts_command(self):
        parsed = {"type": "command", "action": "turn_on"}
        response = mock.MagicMock()
        response.__enter__.return_value = response
        with mock.patch.object(app, "HA_WEBHOOK_URL", "http://ha/webhook/stt"), mock.patch(
            "app.request.urlopen", return_value=response
        ) as urlopen:
            self.assertTrue(app.forward_to_home_assistant(parsed))

        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "http://ha/webhook/stt")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data.decode()), parsed)

    def test_rate_limit_blocks_after_endpoint_limit(self):
        with mock.patch.dict(app.RATE_LIMITS, {"/transcribe": (2, 10.0)}, clear=False):
            self.assertEqual(app.allow_request("127.0.0.1", "/transcribe", now=100.0), (True, 0.0))
            self.assertEqual(app.allow_request("127.0.0.1", "/transcribe", now=101.0), (True, 0.0))
            allowed, retry_after = app.allow_request("127.0.0.1", "/transcribe", now=102.0)

        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1.0)

    def test_read_body_rejects_oversized_request(self):
        handler = object.__new__(app.Handler)
        handler.headers = {"Content-Length": "5"}
        handler.rfile = BytesIO(b"12345")
        handler.send_json = mock.Mock()

        self.assertIsNone(handler.read_body(4))

        handler.send_json.assert_called_once_with({"error": "request body too large"}, status=413)

    def test_read_body_rejects_negative_content_length(self):
        handler = object.__new__(app.Handler)
        handler.headers = {"Content-Length": "-1"}
        handler.rfile = BytesIO(b"")
        handler.send_json = mock.Mock()

        self.assertIsNone(handler.read_body(4))

        handler.send_json.assert_called_once_with({"error": "invalid content length"}, status=400)

    def test_authentication_rejects_missing_token(self):
        handler = object.__new__(app.Handler)
        handler.headers = {}
        handler.send_json = mock.Mock()

        self.assertFalse(handler.authenticated())

        handler.send_json.assert_called_once_with({"error": "unauthorized"}, status=401)

    def test_authentication_accepts_matching_token(self):
        handler = object.__new__(app.Handler)
        handler.headers = {"X-STT-Token": app.AUTH_TOKEN}
        handler.send_json = mock.Mock()

        self.assertTrue(handler.authenticated())

        handler.send_json.assert_not_called()

    def test_html_token_placeholder_is_available_for_injection(self):
        self.assertIn("__AUTH_TOKEN__", app.HTML)


class AudioSessionTest(unittest.TestCase):
    def frame(self, value=0.0):
        pcm = np.full(app.FRAME_SAMPLES, value, dtype=np.float32)
        pcm = (pcm * 32767.0).astype("<i2")
        return pcm.tobytes()

    def test_vad_session_completes_speech_with_prepad(self):
        probs = iter([0.0, 0.0, 0.9] + [0.9] * 11 + [0.0] * app.END_SILENCE_FRAMES)

        def fake_silero_prob(vad, frame, state):
            return next(probs), state

        with mock.patch.object(app, "silero_prob", side_effect=fake_silero_prob), mock.patch.object(
            app, "transcribe_pcm16", return_value={"transcript": "打開客廳燈"}
        ) as transcribe:
            session = app.AudioSession(vad=object())
            results = []
            for _ in range(2):
                results.extend(session.push_pcm16(self.frame(0.0)))
            for _ in range(12):
                results.extend(session.push_pcm16(self.frame(0.2)))
            for _ in range(app.END_SILENCE_FRAMES):
                results.extend(session.push_pcm16(self.frame(0.0)))

        self.assertEqual(results, [{"transcript": "打開客廳燈"}])
        utterance = transcribe.call_args.args[0]
        min_expected_frames = 2 + 12 + app.END_SILENCE_FRAMES
        self.assertGreaterEqual(len(utterance), min_expected_frames * app.FRAME_SAMPLES * 2)

    def test_vad_session_ignores_too_short_speech(self):
        probs = iter([0.9, 0.0] + [0.0] * app.END_SILENCE_FRAMES)

        def fake_silero_prob(vad, frame, state):
            return next(probs), state

        with mock.patch.object(app, "silero_prob", side_effect=fake_silero_prob), mock.patch.object(
            app, "transcribe_pcm16"
        ) as transcribe:
            session = app.AudioSession(vad=object())
            results = []
            results.extend(session.push_pcm16(self.frame(0.2)))
            for _ in range(app.END_SILENCE_FRAMES + 1):
                results.extend(session.push_pcm16(self.frame(0.0)))

        self.assertEqual(results, [])
        transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main()

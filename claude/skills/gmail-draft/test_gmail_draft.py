import base64
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MODULE_PATH = Path(__file__).parent / "scripts" / "gmail_draft.py"
SPEC = importlib.util.spec_from_file_location("gmail_draft", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
gmail_draft = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gmail_draft)


def gmail_payload(part: EmailMessage):
    payload = {
        "mimeType": part.get_content_type(),
        "filename": part.get_filename() or "",
        "headers": [{"name": key, "value": value} for key, value in part.items()],
    }
    if part.is_multipart():
        payload["parts"] = [gmail_payload(child) for child in part.iter_parts()]
    else:
        payload["body"] = {
            "data": base64.urlsafe_b64encode(part.get_payload(decode=True)).decode("ascii")
        }
    return payload


def draft_from_message(message: EmailMessage, labels=None):
    return {
        "id": "draft-1",
        "message": {
            "id": "message-1",
            "threadId": "thread-1",
            "labelIds": labels or ["DRAFT"],
            "payload": gmail_payload(message),
        },
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, draft=None, get_responses=None):
        self.draft = draft
        self.get_responses = list(get_responses or [])
        self.post_calls = []
        self.put_calls = []
        self.get_calls = []

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return FakeResponse({"id": "draft-1"})

    def put(self, *args, **kwargs):
        self.put_calls.append((args, kwargs))
        return FakeResponse({"id": "draft-1"})

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        if self.get_responses:
            return FakeResponse(self.get_responses.pop(0))
        return FakeResponse(self.draft)


ORIGINAL_METADATA = {
    "id": "orig-1",
    "threadId": "thread-1",
    "payload": {
        "headers": [
            {"name": "Message-ID", "value": "<orig@example.com>"},
            {"name": "References", "value": "<a@example.com>\r\n <b@example.com>"},
            {"name": "Subject", "value": "Quote request"},
            {"name": "From", "value": "Customer <customer@example.com>"},
        ]
    },
}


class GmailDraftTests(unittest.TestCase):
    def test_plain_html_related_has_one_cid_image(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "screenshot.png"
            image.write_bytes(b"png")
            message = gmail_draft.build_message(
                "Daniel de Souza <sender@example.com>",
                ["Recipient <recipient@example.com>"],
                [],
                [],
                "Subject",
                "Meaningful plain fallback\n",
                '<p>HTML</p><img src="cid:screenshot">',
                [],
                {"screenshot": image},
            )
            self.assertEqual(message.get_content_type(), "multipart/related")
            children = list(message.iter_parts())
            self.assertEqual(children[0].get_content_type(), "multipart/alternative")
            self.assertEqual(
                [part.get_content_type() for part in children[0].iter_parts()],
                ["text/plain", "text/html"],
            )
            inline = [part for part in message.walk() if part.get("Content-ID")]
            self.assertEqual(len(inline), 1)
            self.assertEqual(inline[0]["Content-ID"], "<screenshot>")
            self.assertEqual(inline[0].get_content_disposition(), "inline")

    def test_regular_attachment_wraps_related_in_mixed_without_duplicate_image(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "screenshot.png"
            attachment = Path(directory) / "report.txt"
            image.write_bytes(b"png")
            attachment.write_text("report", encoding="utf-8")
            message = gmail_draft.build_message(
                "sender@example.com",
                ["recipient@example.com"],
                [],
                [],
                "Subject",
                "Plain",
                '<p>HTML</p><img src="cid:screenshot">',
                [attachment],
                {"screenshot": image},
            )
            self.assertEqual(message.get_content_type(), "multipart/mixed")
            self.assertEqual(next(message.iter_parts()).get_content_type(), "multipart/related")
            inline_names = [
                part.get_filename()
                for part in message.walk()
                if part.get_content_disposition() == "inline"
            ]
            attachment_names = [
                part.get_filename()
                for part in message.walk()
                if part.get_content_disposition() == "attachment"
            ]
            self.assertEqual(inline_names, ["screenshot.png"])
            self.assertEqual(attachment_names, ["report.txt"])

    def test_build_rejects_bad_inline_inputs_and_relative_attachments(self):
        with self.assertRaises(ValueError):
            gmail_draft.build_message(
                "sender@example.com",
                ["recipient@example.com"],
                [],
                [],
                "Subject",
                "Body",
                None,
                [Path("relative.png")],
                {},
            )
        with self.assertRaises(ValueError):
            gmail_draft._parse_inline_images(["not-a-mapping"])

    def test_verify_checks_alternative_cid_exactly_one_and_ordinary_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "screenshot.png"
            attachment = Path(directory) / "report.txt"
            image.write_bytes(b"png")
            attachment.write_text("report", encoding="utf-8")
            sender = "Daniel de Souza <sender@example.com>"
            message = gmail_draft.build_message(
                sender,
                ["Recipient <recipient@example.com>"],
                [],
                [],
                "Subject",
                "Meaningful plain fallback with required text",
                '<p>Required text</p><img src="cid:screenshot">',
                [attachment],
                {"screenshot": image},
            )
            result = gmail_draft.verify_draft(
                draft_from_message(message),
                sender,
                ["recipient@example.com"],
                [],
                [],
                "Subject",
                [attachment],
                {"screenshot": image},
                True,
                True,
                ["Required text"],
            )
            self.assertTrue(all(result["checks"].values()))
            self.assertEqual(result["inline_cids"], ["screenshot"])
            self.assertEqual(result["attachment_filenames"], ["report.txt"])

    def test_verify_rejects_sent_label(self):
        message = gmail_draft.build_message(
            "sender@example.com",
            ["recipient@example.com"],
            [],
            [],
            "Subject",
            "Body",
            None,
            [],
            {},
        )
        with self.assertRaises(gmail_draft.DraftVerificationError):
            gmail_draft.verify_draft(
                draft_from_message(message, ["DRAFT", "SENT"]),
                "sender@example.com",
                ["recipient@example.com"],
                [],
                [],
                "Subject",
                [],
                {},
                True,
                False,
                ["Body"],
            )

    def test_recipientless_draft_is_allowed_and_verifies(self):
        message = gmail_draft.build_message(
            "sender@example.com",
            [],
            [],
            [],
            "Subject",
            "Body",
            None,
            [],
            {},
        )
        self.assertIsNone(message.get("To"))
        result = gmail_draft.verify_draft(
            draft_from_message(message),
            "sender@example.com",
            [],
            [],
            [],
            "Subject",
            [],
            {},
            True,
            False,
            ["Body"],
        )
        self.assertEqual(result["to"], [])
        self.assertTrue(all(result["checks"].values()))

    def test_cli_exposes_only_auth_create_and_update(self):
        command_action = next(
            action
            for action in gmail_draft.parser()._actions
            if getattr(action, "choices", None)
        )
        self.assertEqual(set(command_action.choices), {"auth-check", "create", "update"})
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("users.messages.send", source)
        self.assertNotIn("users.drafts.delete", source)
        self.assertNotIn("/send", source)
        self.assertNotIn("/trash", source)
        self.assertNotIn("snippet", source)

    def test_subject_required_unless_reply_query(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gmail_draft.parse_args(["create", "--plain-body-file", "/b.txt"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            gmail_draft.parse_args(
                ["create", "--subject", "X", "--reply-to-query", "q", "--plain-body-file", "/b.txt"]
            )
        args = gmail_draft.parse_args(
            ["update", "--draft-id", "d", "--reply-to-query", "q", "--plain-body-file", "/b.txt"]
        )
        self.assertIsNone(args.subject)
        self.assertEqual(args.reply_to_query, "q")

    def test_scopes_include_compose_and_readonly(self):
        self.assertEqual(
            gmail_draft.GMAIL_SCOPES,
            [
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.readonly",
            ],
        )

    def test_reply_lookup_fetches_metadata_only_and_builds_headers(self):
        session = FakeSession(get_responses=[{"messages": [{"id": "orig-1"}]}, ORIGINAL_METADATA])
        original = gmail_draft.lookup_reply_target(session, "from:customer@example.com")
        list_call, meta_call = session.get_calls
        self.assertEqual(list_call[1]["params"], {"q": "from:customer@example.com", "maxResults": 1})
        self.assertTrue(meta_call[0][0].endswith("/users/me/messages/orig-1"))
        self.assertEqual(meta_call[1]["params"]["format"], "metadata")
        self.assertEqual(
            meta_call[1]["params"]["metadataHeaders"],
            ["Message-ID", "References", "Subject", "From"],
        )
        reply = gmail_draft.reply_metadata(original, [])
        self.assertEqual(reply["thread_id"], "thread-1")
        self.assertEqual(reply["in_reply_to"], "<orig@example.com>")
        self.assertEqual(
            reply["references"], "<a@example.com> <b@example.com> <orig@example.com>"
        )
        self.assertEqual(reply["subject"], "Re: Quote request")
        self.assertEqual(reply["to"], ["Customer <customer@example.com>"])
        self.assertEqual(
            gmail_draft.reply_metadata(original, ["other@example.com"])["to"],
            ["other@example.com"],
        )

    def test_reply_lookup_errors_on_no_match_and_missing_metadata(self):
        with self.assertRaises(gmail_draft.ReplyLookupError):
            gmail_draft.lookup_reply_target(FakeSession(get_responses=[{}]), "nothing")
        incomplete = {"id": "orig-1", "threadId": "thread-1", "payload": {"headers": []}}
        with self.assertRaises(gmail_draft.ReplyLookupError):
            gmail_draft.lookup_reply_target(
                FakeSession(get_responses=[{"messages": [{"id": "orig-1"}]}, incomplete]), "q"
            )

    def test_reply_subject_does_not_double_existing_re(self):
        original = {
            "thread_id": "t",
            "message_id": "<m>",
            "subject": "RE: Already replied",
            "from": "a@example.com",
            "references": "",
        }
        reply = gmail_draft.reply_metadata(original, [])
        self.assertEqual(reply["subject"], "RE: Already replied")
        self.assertEqual(reply["references"], "<m>")

    def test_update_reply_sends_thread_id_and_verifies_reply_headers(self):
        reply = {
            "thread_id": "thread-1",
            "in_reply_to": "<orig@example.com>",
            "references": "<a@example.com> <orig@example.com>",
            "subject": "Re: Quote request",
            "to": ["customer@example.com"],
        }
        message = gmail_draft.build_message(
            "sender@example.com",
            reply["to"],
            [],
            [],
            reply["subject"],
            "Body",
            None,
            [],
            {},
            reply["in_reply_to"],
            reply["references"],
        )
        self.assertEqual(message["In-Reply-To"], "<orig@example.com>")
        session = FakeSession(draft_from_message(message))
        credentials = SimpleNamespace(_subject="sender@example.com")
        with patch.object(gmail_draft, "api_session", return_value=session):
            result = gmail_draft.write_and_verify(
                credentials,
                message,
                "update",
                "draft-1",
                "sender@example.com",
                reply["to"],
                [],
                [],
                reply["subject"],
                [],
                {},
                True,
                False,
                ["Body"],
                reply,
            )
        self.assertEqual(session.put_calls[0][1]["json"]["message"]["threadId"], "thread-1")
        self.assertEqual(result["thread_id"], "thread-1")
        self.assertEqual(result["original_thread_id"], "thread-1")
        self.assertEqual(result["in_reply_to"], "<orig@example.com>")
        self.assertEqual(result["references"], "<a@example.com> <orig@example.com>")
        self.assertEqual(result["scope"], gmail_draft.GMAIL_SCOPES)
        for check in ("thread_id", "in_reply_to", "references", "reply_subject"):
            self.assertTrue(result["checks"][check], check)
        wrong_thread = draft_from_message(message)
        wrong_thread["message"]["threadId"] = "thread-2"
        with self.assertRaises(gmail_draft.DraftVerificationError):
            gmail_draft.verify_draft(
                wrong_thread, "sender@example.com", reply["to"], [], [],
                reply["subject"], [], {}, True, False, ["Body"], reply,
            )

    def test_update_calls_users_drafts_update_exactly_once_then_reads_back(self):
        message = gmail_draft.build_message(
            "sender@example.com",
            ["recipient@example.com"],
            [],
            [],
            "Subject",
            "Body",
            None,
            [],
            {},
        )
        session = FakeSession(draft_from_message(message))
        credentials = SimpleNamespace(_subject="sender@example.com")
        with patch.object(gmail_draft, "api_session", return_value=session):
            result = gmail_draft.write_and_verify(
                credentials,
                message,
                "update",
                "draft-1",
                "sender@example.com",
                ["recipient@example.com"],
                [],
                [],
                "Subject",
                [],
                {},
                True,
                False,
                ["Body"],
            )
        self.assertEqual(len(session.put_calls), 1)
        self.assertEqual(len(session.post_calls), 0)
        self.assertEqual(len(session.get_calls), 1)
        self.assertEqual(result["operation"], "users.drafts.update + users.drafts.get")


if __name__ == "__main__":
    unittest.main()
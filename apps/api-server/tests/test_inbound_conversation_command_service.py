import unittest

from app.modules.conversation.inbound_command_service import parse_inbound_conversation_command


class InboundConversationCommandServiceTests(unittest.TestCase):
    def test_parse_supports_new_and_reset(self) -> None:
        new_command = parse_inbound_conversation_command(" /new ")
        reset_command = parse_inbound_conversation_command("/reset@FamilyClawBot")

        self.assertIsNotNone(new_command)
        self.assertEqual("new", new_command.name)
        self.assertIsNotNone(reset_command)
        self.assertEqual("reset", reset_command.name)

    def test_parse_does_not_misclassify_regular_text(self) -> None:
        self.assertIsNone(parse_inbound_conversation_command(None))
        self.assertIsNone(parse_inbound_conversation_command(""))
        self.assertIsNone(parse_inbound_conversation_command("new"))
        self.assertIsNone(parse_inbound_conversation_command("/new 请帮我开始"))
        self.assertIsNone(parse_inbound_conversation_command("今天/new 这个话题挺奇怪"))


if __name__ == "__main__":
    unittest.main()

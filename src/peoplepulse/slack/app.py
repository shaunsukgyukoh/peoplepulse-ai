import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from peoplepulse.config import Settings, get_settings
from peoplepulse.messaging.redis_stream import SlackEventPublisher
from peoplepulse.slack.events import normalize_message_event

logger = logging.getLogger("peoplepulse.slack")


def create_app(
    settings: Settings | None = None,
    publisher: SlackEventPublisher | None = None,
) -> App:
    settings = settings or get_settings()
    settings.validate_slack_runtime()
    publisher = publisher or SlackEventPublisher(settings)
    publisher.ping()

    app = App(token=settings.slack_bot_token)

    @app.event("message")
    def handle_message(body: dict, event: dict, logger: logging.Logger) -> None:
        normalized = normalize_message_event(
            body=body,
            event=event,
            employee_hash_key=settings.employee_hash_key,
        )
        if normalized is None:
            return

        event_id = str(normalized.fields["event_id"])
        stream_id = publisher.publish_once(event_id, normalized.fields)
        if stream_id is None:
            logger.info("Duplicate Slack event ignored event_id=%s", event_id)
            return

        # Never log message text or original Slack user/channel identifiers.
        logger.info(
            "Slack message queued event_id=%s stream_id=%s channel_type=%s text_length=%s",
            event_id,
            stream_id,
            normalized.fields["channel_type"],
            normalized.fields["text_length"],
        )

    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    settings.validate_slack_runtime()
    app = create_app(settings=settings)
    logger.info("Starting PeoplePulse Slack listener via Socket Mode")
    SocketModeHandler(app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()

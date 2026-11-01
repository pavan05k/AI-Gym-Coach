import os
import sys

from twilio.rest import Client


def main():
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    api_key_sid = os.environ.get("TWILIO_API_KEY_SID")
    api_key_secret = os.environ.get("TWILIO_API_KEY_SECRET")

    missing = [
        name
        for name, value in {
            "TWILIO_ACCOUNT_SID": account_sid,
            "TWILIO_API_KEY_SID": api_key_sid,
            "TWILIO_API_KEY_SECRET": api_key_secret,
        }.items()
        if not value
    ]
    if missing:
        print(
            "Set these environment variables before running the script: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    token = Client(api_key_sid, api_key_secret, account_sid).tokens.create()

    for server in token.ice_servers:
        urls = server.get("urls", [])
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            if url.startswith("turn:") or url.startswith("turns:"):
                print(f"TURN_SERVER_URL = {url!r}")
                print(f"TURN_SERVER_USERNAME = {server['username']!r}")
                print(f"TURN_SERVER_CREDENTIAL = {server['credential']!r}")
                return 0

    print("Twilio did not return a TURN server.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

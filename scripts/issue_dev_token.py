"""Issue a short-lived JWT for local development only; never expose this as an API."""

import argparse
import time

import jwt

from orchestrator.core.config import Environment, get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--subject", required=True, help="Local user ID to place in the token subject"
    )
    parser.add_argument("--role", choices=("user", "admin"), default="user")
    args = parser.parse_args()

    settings = get_settings()
    if settings.environment != Environment.DEVELOPMENT:
        parser.error("This helper is restricted to ENVIRONMENT=development.")
    now = int(time.time())
    ttl = min(max(60, settings.device_token_ttl_seconds), 900)
    token = jwt.encode(
        {
            "sub": args.subject,
            "role": args.role,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + ttl,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    print(token)


if __name__ == "__main__":
    main()

import argparse
import sys

from firebase_admin import auth

from app.infrastructure.providers.firebase import initialize_firebase


def make_admin(email: str) -> None:
    app = initialize_firebase()
    user = auth.get_user_by_email(email, app=app)
    claims = dict(user.custom_claims or {})
    claims["role"] = "admin"
    auth.set_custom_user_claims(user.uid, claims, app=app)
    print(f"Updated custom claims for {email} ({user.uid}): {claims}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grant Firebase admin role to a user by email."
    )
    parser.add_argument("email", help="Firebase Authentication user email")
    args = parser.parse_args()

    try:
        make_admin(args.email)
    except ValueError as exc:
        print(f"Firebase configuration error: {exc}", file=sys.stderr)
        return 2
    except auth.UserNotFoundError:
        print(f"No Firebase user found for email: {args.email}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to update custom claims: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

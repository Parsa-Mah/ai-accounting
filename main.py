"""Entry point: runs the Accounting web application with uvicorn."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Accounting web application")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--seed", action="store_true", help="Seed the database with demo data")
    args = parser.parse_args()

    if args.seed:
        from app.seed.demo import seed_demo_data

        seed_demo_data()

    from app.main import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()

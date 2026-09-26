import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta
import httpx

from app.config import settings
from app.auth.api_keys import generate_api_key
from app.database.models import User, APIKey, RequestLog
from app.database.repository import init_db, async_session_factory, DatabaseRepository
from app.cache.redis import get_redis
from app.routing.router import router


async def cmd_keys_create(user_id: str, name: str, expires_days: int):
    await init_db()
    if not async_session_factory:
        print("[!] Failed to initialize database.")
        return

    async with async_session_factory() as session:
        repo = DatabaseRepository(session)
        user = await repo.get_user(user_id)
        if not user:
            user = await repo.create_user(user_id, name)

        raw_key, key_hash, prefix = generate_api_key("pllm_")
        expires_at = datetime.utcnow() + timedelta(days=expires_days) if expires_days > 0 else None
        key_id = f"key_{raw_key[5:15]}"

        await repo.create_api_key(
            key_id=key_id,
            user_id=user.id,
            key_hash=key_hash,
            prefix=prefix,
            expires_at=expires_at,
        )
        await session.commit()

        print("\n" + "=" * 60)
        print(" [✓] API Key Created Successfully!")
        print("=" * 60)
        print(f" Key ID:    {key_id}")
        print(f" User ID:   {user_id}")
        print(f" Prefix:    {prefix}")
        print(f" Secret:    {raw_key}")
        print(f" Expires:   {expires_at or 'Never'}")
        print("=" * 60)
        print(" [!] Save this key now — it cannot be retrieved again.\n")


async def cmd_doctor():
    print("\n🔍 Running ProdLLM Gateway Diagnostic Doctor...")
    print("-" * 60)

    # 1. Database Check
    try:
        await init_db()
        print(" [✓] Database:          Connected successfully.")
    except Exception as e:
        print(f" [✗] Database:          Connection failed ({e})")

    # 2. Redis Check
    try:
        r = await get_redis()
        if r:
            await r.ping()
            print(" [✓] Redis:             Connected successfully.")
        else:
            print(" [!] Redis:             Disabled or using in-memory fallback.")
    except Exception as e:
        print(f" [✗] Redis:             Failed ({e})")

    # 3. Provider Credentials
    print(f" [i] Gemini Key:        {'Configured (***)' if settings.GEMINI_API_KEY else 'Not set (Optional)'}")
    print(f" [i] OpenRouter Key:    {'Configured (***)' if settings.OPENROUTER_API_KEY else 'Not set (Optional)'}")
    print(f" [i] Agnes AI Key:      {'Configured (***)' if settings.AGNES_API_KEY else 'Not set (Optional)'}")

    # 4. Upstream Provider Health
    print("\nChecking Upstream Providers:")
    health_results = await router.check_all_health()
    for name, h in health_results.items():
        status_icon = "✓" if h.status == "healthy" else "✗"
        print(f" [{status_icon}] Provider '{name:10}': {h.status.upper()} ({h.latency_ms:.1f}ms) {h.error or ''}")

    print("-" * 60 + "\n")


async def cmd_stats():
    await init_db()
    if not async_session_factory:
        print("[!] Database not available.")
        return

    async with async_session_factory() as session:
        repo = DatabaseRepository(session)
        summary = await repo.get_usage_summary()

        print("\n" + "=" * 60)
        print(" 📊 ProdLLM Gateway — Historical Usage Summary")
        print("=" * 60)
        print(f" Total Requests:          {summary['total_requests']:,}")
        print(f" Total Prompt Tokens:     {summary.get('total_prompt_tokens', 0):,}")
        print(f" Total Completion Tokens: {summary.get('total_completion_tokens', 0):,}")
        print(f" Total Tokens:            {summary['total_tokens']:,}")
        print(f" Avg Latency:             {summary['avg_latency_ms']:.2f} ms")
        print(f" Estimated Virtual Cost:  ${summary['total_cost']:.6f} USD")
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ProdLLM Gateway CLI Administration Tool")
    subparsers = parser.add_subparsers(dest="command")

    # keys command
    keys_parser = subparsers.add_parser("keys", help="Manage API Keys")
    keys_sub = keys_parser.add_subparsers(dest="subcommand")

    create_parser = keys_sub.add_parser("create", help="Generate a new API key")
    create_parser.add_argument("--user-id", required=True, help="User identifier")
    create_parser.add_argument("--name", default="Developer", help="User display name")
    create_parser.add_argument("--expires", type=int, default=30, help="Expiry in days (0 for never)")

    # doctor command
    subparsers.add_parser("doctor", help="Run system diagnostics and provider health checks")

    # stats command
    subparsers.add_parser("stats", help="Display gateway usage analytics")

    # run command
    run_parser = subparsers.add_parser("run", help="Start the gateway server")
    run_parser.add_argument("--host", default=settings.HOST)
    run_parser.add_argument("--port", type=int, default=settings.PORT)
    run_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    if args.command == "keys" and args.subcommand == "create":
        asyncio.run(cmd_keys_create(args.user_id, args.name, args.expires))
    elif args.command == "doctor":
        asyncio.run(cmd_doctor())
    elif args.command == "stats":
        asyncio.run(cmd_stats())
    elif args.command == "run":
        import uvicorn
        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

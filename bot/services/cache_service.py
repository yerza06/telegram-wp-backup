import asyncio
import shutil

from bot.core.config import settings
from bot.services.backup_service import operation_lock


async def flush_cache() -> str:
    if not shutil.which("wp"):
        raise RuntimeError(
            "WP-CLI не найден. Установите по инструкции: https://wp-cli.org/"
        )

    if operation_lock.locked():
        raise RuntimeError(
            "Невозможно очистить кэш: в данный момент выполняется бэкап или восстановление."
        )

    proc = await asyncio.create_subprocess_exec(
        "sudo", "-u", "www-data",
        "wp", "cache", "flush",
        f"--path={settings.site.wp_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "wp cache flush завершился с ошибкой")

    return stdout.decode().strip()

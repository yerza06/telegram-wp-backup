import asyncio
import shutil


async def get_disk_usage() -> str:
    proc = await asyncio.create_subprocess_exec(
        "df", "-h",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"df -h failed: {stderr.decode()}")
    return stdout.decode()


def check_free_space(path: str, min_mb: int) -> bool:
    usage = shutil.disk_usage(path)
    return usage.free >= min_mb * 1024 * 1024


def free_space_mb(path: str) -> int:
    return shutil.disk_usage(path).free // (1024 * 1024)

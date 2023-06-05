import asyncio
import json
import time
from typing import List, Dict
import aiohttp


async def do_post(url, body, params=None) -> Dict | List:
    if not isinstance(body, str):
        body = json.dumps(body)
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=body, params=params) as response:
            return await response.json()


async def do_get(url, params=None) -> Dict | List:
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            return await response.json()

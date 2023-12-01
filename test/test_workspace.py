import sys
import os
import logging
import asyncio
import time
import unittest

dir_path = os.path.dirname(os.path.realpath(__file__))

sys.path.append("{}/../src/".format(dir_path))

from aios_kernel import WorkspaceEnvironment

async def test_workspace():
    test_env = WorkspaceEnvironment("test")
    test_env._add_document_dir(f"{dir_path}/../rootfs/test_doc")
    test_env._start_scan_document()
    catalogs = await test_env.get_knowledege_catalog()
    print(catalogs)
    asyncio.sleep(60*60)


if __name__ == "__main__":
    asyncio.run(test_workspace())
    print("OK!")
    time.sleep(60*60)



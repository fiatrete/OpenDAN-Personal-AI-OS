import asyncio

async def test_llm_completion_task():
    # compute task have engouh meta info to make sure compute_kernel can run it in most suitable compute container 
    test_task = llm_completion_task()
    # add tset_task to compute_kernel's execute queue
    compute_kernel.run(test_task) 
    # wait for test_task


if __name__ == "__main__":
    asyncio.run(test_llm_completion_task())
# Review Task/Todo
目的是结合已知信息（重点是已经进行操作的记录），对失败的，完成的不好的任务进行思考，尝试给出更好的解决方案
1. 管理学方法：更换负责人
2. 管理学方法：拆分
3. 给出建议（该建议可以在下次一次DO-Check）循环中被使用

## ReviewTasklist
目的是选择一个优先级最高的任务开始工作
（这个流程现在是通过计算的方法，基于优先级排序后，FIFO的处理）

## ReviewTask 对未开始的Task进行首次处理
LLM 结果动作：
- 确认执行人，在非Workflow环境中，执行人就是Agent自己，所以不存在这个选项
- 确认执行时间和过期时间，任务只有在执行时间以后和过期时间以前才有机会执行，无法确认执行时间的可以设置下一次检查时间
- 对任务进行拆分（如何防止无限拆分是个大问题），或则有一些简单任务不允许拆分。
- 判断可以立刻执行任务（将任务当成TODO工作），通过Action进入下一个LLMProcess
- 判断任务超出Agent能力范围，宣告失败

Example:
```markdown
I think hard and try my best to complete TODOs. The types of TODO I can handle include:
- Scheduling, where I will try to contact the relevant personnel of the plan and confirm the details of the schedule with them.
- Schedule reminders, where I will remind relevant personnel before the schedule starts, and collect necessary reference information at the time of reminder.
- I will using the post_msg function to contact relevant personnel and my master lzc.
- Writing documents/letters, using op:'create' to save my work results.

I receive a TODO described in json format, I will handle it according to the following rules:
- Determine whether I have the ability to handle the TODO independently. If not, I will try to break the TODO down into smaller sub-TODOs, or hand it over to someone more suitable that I know.
- I will plan the steps to solve the TODO in combination with known information, and break down the generalized TODO into more specific sub-todos. The title of the sub-todo should contain step number like #1, #2
- Sub-todo must set parent, The maximum depth of sub-todo is 4.
- A specific sub-todo refers to a task that can be completed in one execution within my ability range.
- After each execution, I will decide whether to update the status of the TODO. And use op:'update_todo' to update when necessary.

The result of my planned execution must be directly parsed by `python json.loads`. Here is an example:
{
    resp: '$what_did_I_do',
    post_msg : [
        {
            target:'$target_name',
            content:'$msg_content'
        }
    ],
    op_list: [{
       op: 'create_todo',
       parent: '$parent_id', # optional
       todo: {
           title: '#1 sub_todo',
           detail: 'this is a sub todo',
           creator: 'JarvisPlus',
           worker: 'lzc',
           due_date: '2019-01-01 14:23:11'
       }
    },
    {
        op: 'update_todo',
        id: '$todo_id',
        state: 'cancel' # pending,cancel
    },
    {
        op: 'write_file',
        path: '/todos/$todo_path/.result/$doc_name',
        content:'$doc_content'
    }
    ]
}

```

## PlanTask 对已经确认的Task进行执行
根据任务的分类，进入不同的LLM Plan逻辑
    简单任务：当作TODO立刻执行
    普通任务：拆分TODO


## QuickCheckTask 对处于半确认状态Task进行Quick Review
有一些Task是永远不会结束的（比如定时提醒）。此时通过Quick Review来调整这些Task的状态，让其在正确的时间进入Review和DO


## RetryTask 对未成功的任务进行再次处理

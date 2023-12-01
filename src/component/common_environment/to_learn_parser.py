 # 尝试自我学习，会主动获取、读取资料并进行整理
    # LLM的本质能力是处理海量知识，应该让LLM能基于知识把自己的工作处理的更好
    async def do_self_learn(self) -> None:
        # 不同的workspace是否应该有不同的学习方法？
        workspace = self.get_workspace_by_msg(None)
        hash_list = workspace.kb_db.get_knowledge_without_llm_title()
        for hash in hash_list:
            if self.agent_energy <= 0:
                break

            knowledge = workspace.kb_db.get_knowledge(hash)
            if knowledge is None:
                continue

            full_path = knowledge.get("full_path")
            if full_path is None:
                continue

            if os.path.exists(full_path) is False:
                logger.warning(f"do_self_learn: knowledge {full_path} is not exists!")
                continue

             #TODO 可以用v-db 对不同目录的名字进行选择后，先进行一次快速的插入。有时间再慢慢用LLM整理
            result_obj = await self._llm_read_article(knowledge,full_path)

            #根据结果更新knowledge
            if result_obj is not None:
                workspace.kb_db.set_knowledge_llm_result(hash,result_obj)
                # 在知识库中创建软链接
                path_list = result_obj.get("path")
                new_title = result_obj.get("title")
                if path_list:
                    for new_path in path_list:
                        full_new_path = f"/knowledge{new_path}/{new_title}"
                        await workspace.symlink(full_path,full_new_path)
                        logger.info(f"create soft link {full_path} -> {full_new_path}")


            self.agent_energy -= 1

            # match item.type():
            #     case "book":
            #         self.llm_read_book(kb,item)
            #         learn_power -= 1
            #     case "article":
            #
            #         self.llm_read_article(kb,item)
            #         learn_power -= 1
            #     case "video":
            #         self.llm_watch_video(kb,item)
            #         learn_power -= 1
            #     case "audio":
            #         self.llm_listen_audio(kb,item)
            #         learn_power -= 1
            #     case "code_project":
            #         self.llm_read_code_project(kb,item)
            #         learn_power -= 1
            #     case "image":
            #         self.llm_view_image(kb,item)
            #         learn_power -= 1
            #     case "other":
            #         self.llm_read_other(kb,item)
            #         learn_power -= 1
            #     case _:
            #         self.llm_learn_any(kb,item)
            #         pass


    async def do_blance_knowledge_base(selft):
        # 整理自己的知识库(让分类更平衡，更由于自己以后的工作)，并尝试更新学习目标
        current_path = "/"
        current_list = kb.get_list(current_path)
        self_assessment_with_goal = self.get_self_assessment_with_goal()
        learn_goal = {}


        llm_blance_knowledge_base(current_path,current_list,self_assessment_with_goal,learn_goal,learn_power)

        # 主动学习
        # 方法目前只有使用搜索引擎一种？
        for goal in learn_goal.items():
            self.llm_learn_with_search_engine(kb,goal,learn_power)
            if learn_power <= 0:
                break


    def parser_learn_llm_result(self,llm_result:LLMResult):
        pass

    async def gen_known_info_for_knowledge_prompt(self,knowledge_item:dict,temp_meta = None,need_catalogs = False) -> AgentPrompt:
        workspace =self.get_workspace_by_msg(None)
        kb_tree = await workspace.get_knowledege_catalog()


        known_obj = {}
        title  = knowledge_item.get("title")
        if title:
            known_obj["title"] = title
        summary = knowledge_item.get("summary")
        if summary:
            known_obj["summary"] = summary
        tags = knowledge_item.get("tags")
        if tags:
            known_obj["tags"] = tags
        if need_catalogs:
            catalogs = knowledge_item.get("catalogs")
            if catalogs:
                known_obj["catalogs"] = catalogs

        if temp_meta:
            for key in temp_meta.keys():
                known_obj[key] = temp_meta[key]

        org_path = knowledge_item.get("full_path")
        known_obj["orginal_path"] = org_path
        know_info_str = f"# Known information:\n## Current directory structure:\n{kb_tree}\n## Knowlege Metadata:\n{json.dumps(known_obj)}\n"
        return AgentPrompt(know_info_str)

    async def _llm_read_article(self,knowledge_item:dict,full_path:str) -> ComputeTaskResult:
        # Objectives:
        #   Obtain better titles, abstracts, table of contents (if necessary), tags
        #   Determine the appropriate place to put it (in line with the organization's goals)
        # Known information:
        #   The reason why the target service's learn_prompt is being sorted
        #   Summary of the organization's work (if any)
        #   The current structure of the knowledge base (note the size control) gen_kb_tree_prompt (when empty, LLM should generate an appropriate initial directory structure)
        #   Original path, current title, abstract, table of contents

        # Sorting long files (general tricks)
        #   Indicate that the input is part of the content, let LLM generate intermediate results for the task
        #   Enter the content in sequence, when the last content block is input, LLM gets the result


        #full_content = item.get_article_full_content()
        workspace = self.get_workspace_by_msg(None)
        full_content_len = self.token_len(full_content)

        if full_content_len < self.get_llm_learn_token_limit():

            # 短文章不用总结catelog
            #path_list,summary = llm_get_summary(summary,full_content)
            #prompt = self.get_agent_role_prompt()
            prompt = AgentPrompt()
            prompt.append(self.get_learn_prompt())
            known_info_prompt = await self.gen_known_info_for_knowledge_prompt(knowledge_item)
            prompt.append(known_info_prompt)
            content_prompt = AgentPrompt(full_content)
            prompt.append(content_prompt)
            env_functions = None
            #env_functions,function_len = workspace.get_knowledge_base_ai_functions()
            task_result:ComputeTaskResult = await self.do_llm_complection(prompt,is_json_resp=True)
            if task_result.result_code != ComputeTaskResultCode.OK:
                result_obj = {}
                result_obj["error_str"] = task_result.error_str
                return result_obj

            result_obj = json.loads(task_result.result_str)
            return result_obj

        else:
            logger.warning(f"llm_read_article: article {full_path} use LLM loop learn!")
            pos = 0
            read_len = int(self.get_llm_learn_token_limit() * 1.2)

            temp_meta_data = {}
            is_final = False
            while pos < str_len:
                _content = full_content[pos:pos+read_len]
                part_cotent_len = len(_content)
                if part_cotent_len < read_len:
                    # last chunk
                    is_final = True
                    part_content = f"<<Final Part:start at {pos}>>\n{_content}"
                else:
                    part_content = f"<<Part:start at {pos}>>\n{_content}"

                pos = pos + read_len
                prompt = AgentPrompt()
                prompt.append(self.get_learn_prompt())
                known_info_prompt = await self.gen_known_info_for_knowledge_prompt(knowledge_item,temp_meta_data)
                prompt.append(known_info_prompt)
                content_prompt = AgentPrompt(part_content)
                prompt.append(content_prompt)
                #env_functions,function_len = workspace.get_knowledge_base_ai_functions()
                task_result:ComputeTaskResult = await self.do_llm_complection(prompt,is_json_resp=True)
                if task_result.result_code != ComputeTaskResultCode.OK:
                    result_obj = {}
                    result_obj["error_str"] = task_result.error_str
                    return result_obj

                result_obj = json.loads(task_result.result_str)
                temp_meta_data = result_obj
                if is_final:
                    return result_obj

            return None


    async def do_self_think(self):
        session_id_list = AIChatSession.list_session(self.agent_id,self.chat_db)
        for session_id in session_id_list:
            if self.agent_energy <= 0:
                break
            used_energy = await self.think_chatsession(session_id)
            self.agent_energy -= used_energy

        todo_logs = await self.get_todo_logs()
        for todo_log in todo_logs:
            if self.agent_energy <= 0:
                break
            used_energy = await self.think_todo_log(todo_log)
            self.agent_energy -= used_energy

        return
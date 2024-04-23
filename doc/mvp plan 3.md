# Proposal for Adjusting the Goals for Version 0.5.2

Dear Team,

Given the recent launch of OpenAI's new version in early November 2023, many of us may have felt a profound shift in the industry. As the world changes, I believe we should adapt accordingly. Here are some of my thoughts:

1. **Affirmation of Our Path**: OpenAI's latest release, particularly the functionalities of the so-called GPTs Agent platform, is largely similar to our 0.5.1 version released on September 28th. This strongly affirms the correctness of our direction. OpenAI has done a great job educating the market about the Agent, so we no longer need to emphasize the correct use of LLM based on the Agent through version releases. This part of user education product design can be simplified.

2. **Innovation in Version 0.5.2**: For our new version (0.5.2), besides maintaining the combinational advantages brought by private deployment of LLM, I believe we need to implement some of the innovative ideas we've discussed about the Agent. This is crucial to maintaining our leading position and avoiding the impression that OpenDAN is merely a follower of GPTs.

3. **Integration of OpenAI's New Capabilities**: We should fully integrate the new capabilities brought by OpenAI's latest release, especially the longer Token Windows, GPT-V, and Code-interpreter. I believe these new features can effectively solve some known issues.

Therefore, I propose to adjust the goals and plans for version 0.5.2. Here are the core objectives:

- Aim to release version 0.5.2 by the end of November, focusing on:
  - Launching a new Agent with Autonomous capabilities and multi-Agent collaboration based on Workspace.
  - The integrated product of 0.5.2 will be a private deployment email analysis Agent for small and medium-sized enterprises. This will allow any company to better support its CEO and other management positions through LLM while ensuring privacy and security.
  - (Optional) By combining LLM and AIGC, build an Agent-based personalized AIGC application, such as a "children's audio picture book" generator that includes both text-to-image and text-to-sound.
  - (Optional) Through multi-Agent collaboration, fully utilize the capabilities of GPT4-Turbo, and attempt to let AI and engineers collaborate on research and development tasks based on Git.

The detailed version plan is as follows:

## MVP plan adjustment

In order to keep the list below too long, the system distributed version is 0.5.3, I think we will open another ISSUE discussion and record, this list does not include.

The modules that are not specially explained are components completed in the 0.5.2 plan


- [x] AIOS Kernel
    - [x] Basic Agent,@waterflier, A2
        - [x] Python Agent Extend, @wugren, S2
    - [x] Basic Workflow,@waterflier, A2
    - [ ] Workflow Refactor,@waterflier, A2
    - [x] AI Functions,@waterflier,A2
        - [ ] Upgrade to GPT4 tools API,S2
    - [x] AI Environments,@waterflier, A2
        - [x] Celender Environment,@waterflier, S2
        - [x] Contanct Manage Support,@waterflier, S2
        - [x] AI Shell Enviroment,@waterflier, S1
    - [x] Upgrade Agent Working Cycle
        - [x] Process Message,@waterflier,A2
            - [x] Process Group Message,@waterflier,A2
        - [ ] Process Event,(0.5.3)
        - [ ] Completion of self-drive,@waterflier,A4
        - [ ] Self-learn,@weaterflier,A2
        - [ ] Introspection,@waterflier,A2
        - [ ] Workspace Environment
            - [ ] Task/TODO Manager,@waterflier, A2
            - [x] Local File System,@waterflier, S1
            - [ ] Web Search, A4
            - [ ] Code Interpeter (The first implementation can be based on Openai), A4
            - [ ] Query SQL DB, S1
    - [x] AI BUS,@waterflier, A2
        - [ ] Agent Message MIME Support (Image,Video,Audio), A3
        - [x] Connect to Human, @waterflier,A2
    - [x] Chatsession,@waterflier, S2
        - [ ] Compress Chatsession By Text Summary, @waterflier, A2
    - [ ] Knowlege Base,@lurenpluto ,@photosssa
        - [x] Knowledge Base Frame,@photosssa,A3
        - [x] Knowledge Base Object Store,@lurenpluto ,A4
        - [x] Knowledge Base Basic Pipline,@photosssa ,A3
        - [ ] Customize pipeline,@photosss,A4
        - [ ] Support Local Text Search,A4
        - [x] Text Summary Pipline,@waterflier, A2
        - [ ] Text Parser Support
            - [x] PDF Parser,@waterflier,S2
            - [ ] doc Parser,S4
            - [x] MD Parser,@waterflier,S1
            - [ ] Source Code Parser,S4
            - [ ] Image Parser (Base on GPT-V),(S2)
            - [ ] Video Parser (Base on GPT-V), (S4)
    - [ ] Personal AIGC Models
        - [ ] Stable Diffusion Controler Agent (Optional),A6
- [x] AI Compute System,@waterflier, A2
    - [x] Scheduler,@streetycat, A2
    - [x] LLM Kernel
        - [x] GPT4 (Cloud),@waterflier, S1
        - [x] LLaMa2,@streetycat, A2
        - [ ] Claude2, S2
        - [ ] Falcon2, S2
        - [ ] MPT-7B, S2
        - [ ] Vicuna, S2
    - [x] Embeding, @lurenpluto , A4
    - [x] Txt2img,@glen0125,A4
        - [ ] Support DALL-e, @glen0125, S2
    - [x] Img2txt,based on GPT4-V,@alexsunxl S2
    - [x] Txt2voice,@wugren A3
        - [ ] Txt2Voice,base on OpenAI, @wugren A2
    - [ ] Voice2txt, base on OpenAI, A2
    - [ ] Language Translate (Pending)
- [ ] Build-in Service
    - [x] Spider,@alexsunxl, A2
        - [x] E-mail Spider,@alexsunxl, S4
    - [x] Agent Message Tunnel Frame,@waterflier, A2
        - [x] E-mail Tunnel,@waterflier,A2
        - [x] Telegram Tunnel,@waterflier,S2
        - [ ] Discord Tunnel,S2
    - [ ] Home IoT Environment (0.5.3), A4
        - [ ] Compatible Home Assistant (0.5.3), A4
- [ ] Build-in Agents/Apps
    - [x] Agent Mia: Personal Information Assistant,@photosssa,@lurenpluto , A2
    - [x] Agent Jarvis: Peersonal Bulter & Assistant ,@waterflier, A2
    - [ ] A Agent Can Create Other Agent,@wugren, A3
    - [ ] App: Personal Station (0.5.3),A4+S4
- [ ] UI
    - [x] CLI UI (aios_shell),@waterflier,S2
    - [ ] Web UI ,@alexsunxl,S4
    - [ ] OpenDAN Desktop Installer,@alexsunxl+@waterflier,S4
- [x] 0.5.1 Integration Test 
    - [x] Workflow -> AI Agent -> AI Agent,@waterflier,S1
    - [x] Spider -> Pipline -> Knowledge Base,@photosssa,S2
    - [x] AI Agent <- Functions <- Knowledge Base,@lurenpluto,S2
- [x] 0.5.2 Integration Test 
    - [ ] Email Agent/CEO assistant,S4
    - [ ] My AIGC Assistant (optional), S8    
    - [ ] My Software Company(Advance Workflow demo) (optional), S8
- [ ] SDK
    - [x] Workflow SDK,@waterflier, A2
    - [ ] Agent SDK,@waterflier, A2
    - [ ] AI Environments SDK (0.5.2), A2
    - [ ] Compute Kernel SDK (0.5.3), A2
- [ ] Document (>0.5.2)
    - [ ] System design document, including the design document of each subsystem
    - [ ] Installation/use document for end users
    - [ ] SDK document for developers

## Some Explanation
### Upgrade Agent Working Cycle
The goal is to transform the Agent from a passive message-handling Assistant to an actively acting Agent based on roles. The concept of the relevant modules mainly involves the Agent's behavior patterns (4 types), the Agent's capabilities, and the Agent's memory management (learning and introspection).

For a detailed introduction, refer here: https://github.com/fiatrete/OpenDAN-Personal-AI-OS/issues/91

### Workspace Environment
The Workspace supports the implementation of the Agent Working Cycle design. Its core abstraction is defined as: saving the shared state needed for Agent collaboration and providing the basic capabilities for Agents to complete their work. I carefully referenced AutoGPT in the design. The difference between Workspace and AutoGPT is the emphasis on collaboration (Agent with Agent, Agent with humans). After contemplation, the Workspace primarily consists of the following components:

1. Task/Todo manager, representing the unfinished tasks in the Workspace.
2. Saving work logs.
3. Saving learning outcomes and records of known documents.
4. Ability to access the Knowledge Base (RAG support).
5. Virtual file system for saving any work outcomes.
6. A set of SQL-based databases to save any structured data.
7. Real-time internet search capability.
8. Ability to use existing internet services.
9. Ability to use major blockchain systems (Web3).
10. Ability to write/improve code (based on git), run code, and publish services.
11. Communication capabilities with the outside world.
12. Ability to use social networks.


Each Agent has its own private Workspace, not shared with others. I hope to achieve diversity through the combination of "Agent and Workflow Role". Each user "trains" different Agents through their usage habits, and then these Agents collaborate to complete complex tasks defined in the Workflow. The final results of these complex tasks can reflect the user's inherent personality and preferences.

This component design also reflects my thoughts on the key question, "What capabilities should we endow an Agent with, and how do we control the security boundaries when it transitions from a consultant to a steward?" It's not a simple question, so I anticipate this component will continue to iterate in the future.

### Agent Message MIME Support

Agent Message MIME Support means that Agents can handle multiple types of messages, including images, videos, audio, files, etc. For most Agents, this requires adding a customizable standard step of parsing messages in the message handling process. The input of this step is the message's MIME type, and the output is the text content of the message. This step can be implemented by calling the text_parser module.

Another core requirement of MIME support is to use a unified method to save these non-text content data.

### Text base Knowledge Base

In 0.5.1, we mainly implemented RAG based on the popular Embedding + vector database solution. Through practice, we found that this solution did not fully utilize the potential of LLM, so I want to introduce two new modes to further enhance RAG:

1. Build a local text search engine that LLM can use for proper local searches when needed.
2. Assuming LLM will become cheaper in the future, let LLM learn all the documents once and organize the learning results by directory structure (Text Summary). LLM can use browsing methods to find the information it needs.

#### Text Parser Support

Both MIME Support and Text-based Knowledge Base require the system to support converting various document formats into text that can express semantics as much as possible. This component, known as TextParser, should be implemented as an open and extensible framework, given the vast amount of digital content that exists in different formats.

#### Local Text Search

Using traditional inverted index technology to save all document content locally and provide rapid local search capabilities. The implementation of this component can refer to ElasticSearch.

#### Text Summary

Using the capabilities of LLM to learn all the documents and then save the learning results locally. This behavior can be considered "Self-Learn". Users can let Agents responsible for organizing materials use different prompts according to the purpose of organizing the materials to obtain more targeted results.

### Stable Diffusion Controler Agent

Practice the concept of "Agent as a new era method of using computing", replacing the complex Stable Diffusion WebUI with an easy-to-use Agent. Help users complete complex AIGC tasks and build a paradigm. This paradigm can cover the entire process of AIGC: LORA training, use, model downloading, plugin downloading, generation of prompt words, selection of AIGC results.

### Email Agent/CEO assistant

The integrated test product of 0.5.2, aimed at private deployment for small and medium-sized enterprises, is a CEO Assistant that can read all company emails and materials. I am writing a detailed product document, which is not elaborated here.


----------------------------------------


I look forward to hearing your thoughts on these proposed adjustments.


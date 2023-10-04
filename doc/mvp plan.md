# OpenDAN Basic Planning of MVP 
0.5.1 Implement data capture into Knownlege-Base(KB) via Spider, followed by access by AI Agent  (35%)
0.5.2 Build a Personal-Center based on the KB and associate the AI Agent with accessible telgram accounts (30%)
0.5.3 Release for waitlist （5%）
0.5.4 First public release (10%)
0.5.5 Incorporate modifications after the first public version, workload depends on feedback (15%)
0.5.6 Official version of MVP (5%)

# Basic Architecture
(TODO)

# R&D Process Management
Based on the project management module provided by SourceDAO, explore a new open source R&D process of "open source is mining".
0. Confirming Version Leader based on committee election.
1. Module (task division): Divide the system's futures into independent modules as much as possible, the development workload should be at the level of 1 person for 2-3 weeks.
2. Discussion: Discuss whether the module division is reasonable, and design it's *BUDGET* based on the difficulty of the module and its importance to the current version (most important step)
3. Recruit module PM. The module PM is responsible for the module's test delivery: completing the set functions, constructing the basic tests, and passing the self-tests. Testing should retain at least 30% of development resources.
4. For the completed module, PM should write and publicize the Project Proposal. It contains more detailed about module goals + design ideas, participating teams (if any, there should also be a preliminary division of work within the team and calculation of contribution value), and acceptance plan design.
5. The PM completes development and self-testing. Mark the module is *DONE*.
6. Version Leader organizes the acceptance of the module (a dedicated acceptor can be appointed).
7. Version Leader organizes integration testing according to the completion situation, and the module PM fixes BUGs. The test results can be used in the nightly-channel of OpenDAN.
8. After the test passes, the Version Leader announces the version release, anyone can use this from release-chanel.
9. The committee accepts the version after the release effect. After acceptance, all participants can extract contribution rewards.

Difficulty is expressed in the mode of requirement engineer level * time (in weeks, less than 1 week is counted as 1 week). 1 week of work time is calculated as 20 hours.


**Below is the module division design for version 0.5.1.**

# Package Management (Architect*2)
The package management system provides basic package definition and local lookup functionality.

The types of packages are
1. Agent
2. Function
3. Service
4. App
5. Models (various AI models)

The system itself is upgraded on this basis

# Agent Management (Senior*1)
Define Agent package, and give it to the package management system for publishing/download/installation/running

## Some pure prompt word engineering Agent (ordinary*1)
Can refer to the existing implementation of ChatGPT-Next-Web, mainly to let the system run as soon as possible

# Agent (AI) Runtime (Architecture*2)
Implementing the Agent as a person to run is an important basic component
The Agent is an instance of a person, and the contents of all its sessions are interconnected. We can clone a new person based on an existing Agent, and this new Agent runs in a new container inherited from the old agent.
- Wrap LLM Kernel
- Manage chat-session
- Manage memory (one of the difficulties, different from Knowlege-Base)
- Manage identity and permissions
- Manage logs, for the convenience of development and debugging, we can see all the details of the key operation and self-thinking of the Agent.

# Agent Work Flow (Architecture*2)
A team of AI Agents completes a complex task
Understanding this goal can better design the Agent running container
*Next version*

# LLM Kernel Packaging (Architecture*1)
Encapsulate LLM, support Agent to use different LLM cores. We can support the GPT4 first.

## Local LLM Integration (Senior*2)
If the integration is convenient, we can also integrate a local LLM core to see the effect as soon as possible.

# Function Management (Architecture*1)
Define Function, Function itself is a stateless passive calculation. Easy to be recognized and called by Agent.
Function management needs to design the basic structure of Function, implement cloth/download/installation/running based on package management

## Some basic standard Functions (Senior*2)
Can refer to some existing work, the main work in the early stage is standardization, as much as possible in information reading, the write operation that needs to be authorized by users needs to be promoted for consideration
Get the physical information of the specified location: time, temperature, humidity

# Compute Runtime  (Architecture*1)
Except for the Agent, all components run in isolated running containers
The Agent also runs in a container, and its isolation conditions may be stricter than the running container.
Built based on docker,

# Compute Task Manager (Architecture*2)
Manage computational tasks that require more computational resources.
Compute tasks can be completed locally or on other devices.
Insufficient computing resources is the norm, and scheduling work should be done here. Normal queue, give way to urgent short tasks when necessary.

# Spiders 
## Spider Basic Architecture (Architecture*1 )
## Local Storage Format Based on NamedObject Theory (Architecture*1 )
## Email-Spider Senior*1
No threshold at all, mainly to run the framework
## Twitter-Spider Senior*2
For the convenience of ordinary users to install, do not use twitter api
But if it is really impossible to complete, then use twitter api (difficulty drops to ordinary*2)
## Facebook-Spider Senior*2
For the convenience of ordinary users to install, do not use facebook api
But if it is really impossible to complete, then use facebook api (difficulty drops to ordinary*2)

# Embedding Pipelines
## Piplene Basic Architecture  (Architecture*3)
NamedObject+RawData => Vector DB
## Image-Embedding pipeline  (Senior*3)
Implement Image vectorization pipeline (focus)
## Doc-Embedding pipeline  (Senior*3)
Implement Text vectorization pipeline
## Code-Embedding pipeline  (Senior*2)
## Video-Embedding pipeline  (Senior*3)
## Audio-Embedding pipeline  (Senior*3)
 
# Knowledge Base (Architecture*2)
Provide a unified interface, support switching vector database kernel
Integrate open source vector database (pay attention to Lience selection)

When designing the interface, prepare for future access control

# 0.5.1 Integration Test (Senior*3)
Can be divided into two parts
1.Spider -> Pipline -> Knowledge Base
2.AI Agent <- Functions <- Knowledge Base
3.WebUI (not necessary)

## Basic OS System Construction (Architecture*1)
The MVP version will not build a very serious system, the main goal is to set up an integrated test environment.

# AI Gateway(Network OS BUS)
Obtain data by recognizing network data
The Gateway also provides an external access entrance for the entire system, and access control can be unified.
Provides the bus abstraction in the network operating system (the network cable is the bus), devices within the Zone are recognized by the system as plug-and-play devices, and can be called by applications/Agents
*Next version*

# AI Browser
By cooperating with the browser, save the web pages that users have seen to capture data
*Next version*

# IoT Functions
On the one hand, define standard Functions according to device types
On the other hand, it is necessary to crack some existing IoT devices so that they can be connected to the AI Gateway and can be controlled by the Agent
*Next version*

# Personal Lora Model Building
*Next version*

## Personal Image Lora
## Personal Voice Lora

# Permission and Privacy Management
*Next version*

# AI Capability (Function) Integration
*Next version*

## Text2Image
Stable Diffusion core
Stable Diffusion model management
## Text2Voice


# Telegram API Integration
*Next version*

# Web Version Personal Center
*Next version*

# Built-in Agents
*Next version*

# Built-in APPs
*Next version*



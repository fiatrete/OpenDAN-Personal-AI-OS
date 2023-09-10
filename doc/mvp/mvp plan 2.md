# Overview

The core goal of version 0.5.1 is to turn the concept of AIOS into code and get it up and running as quickly as possible. After three weeks of development, our plans have undergone some changes based on the actual progress of the system. Under the guidance of this goal, some components do not need to be fully implemented. Furthermore, based on the actual development experience from several demo Intelligent Applications, we intend to strengthen some components. This document will explain these changes and provide an update on the current development progress of MVP(0.5.1,0.5.2)

The previous plan, please see here: [MVP Plan](./mvp%20plan.md)

# Progress Status of MVP

- Each module includes whether the current version goals have been met, the current person in charge, and workload assessment.
- Modules that are not marked for version 0.5.2 and do not have a designated person in charge are modules for which we are currently recruiting contributors.
- Modules that have not been completed but already have a designated person in charge are modules that are currently in development.

- [x] AIOS Kernel
    - [x] Agent,@waterflier, A2
        - [ ] Optimization of system prompts,A2
    - [x] Workflow,@waterflier, A2
    - [x] AI Environments,@waterflier, A2
        - [x] Celender Environment,@waterflier, S2
            - [ ] Compatible with common Celender services(0.5.2),A2
                - [ ] Microsoft Outlook Calendar, S2
                - [ ] Google Calendar, S2
                - [ ] Apple Calendar, S2    
        - [ ] Workspace Environment(0.5.2) @waterflier, A2
    - [ ] AI Functions,@waterflier,A2
        - [ ] Basic AI Functions(0.5.2)
    - [x] AI BUS,@waterflier, A2
    - [x] Chatsession,@waterflier, S2
    - [ ] Knowlege Base,@lurenpluto ,@photosssa, A8
    - [ ] Personal Models(>0.5.2),A8
- [ ] Frame Services(0.5.2)
    - [ ] Kernel Service
        - [ ] System-Call Interface,A2
        - [ ] Name Service,A4
        - [ ] Node Daemon,A2
        - [ ] ACL Control,A4
        - [ ] Contact Manager,A2
    - [ ] Runtime Context (0.5.2),A4
    - [ ] Package System,@waterflier, A2+S4
- [x] AI Compute System,@waterflier, A2
    - [ ] Scheduler,@streetycat, A2
    - [x] LLM
        - [x] GPT4 (Cloud),@waterflier, S1
        - [ ] LLaMa2,@streetycat, A2
        - [ ] Claude2, S2
        - [ ] Falcon2, S2
        - [ ] MPT-7B, S2
        - [ ] Vicuna, S2
    - [ ] Embeding,@photosssa,@lurenpluto , A4
    - [ ] Txt2img,@glen0125,A4
    - [ ] Img2txt(0.5.2),A3
    - [ ] Txt2voice,A3
    - [ ] Voice2txt, @wugren,A3
    - [ ] Language Translate (Pending)
- [x] Storage System
    - [ ] DFS (0.5.2),A4
    - [ ] Object Storage, @lurenpluto ,A2
    - [ ] D-RDB (0.5.2),A2
    - [ ] D-VDB,@lurenpluto , A4
- [ ] Embeding Piplines,@photosssa, A2
- [ ] Network Gateway,A6
    - [x] NDN Client, @waterflier, A1
- [ ] Build-in Service
    - [x] Spider,@alexsunxl, A2
        - [x] E-mail Spider,@alexsunxl, S2
        - [ ] Telegram Spider,S2
        - [ ] Twitter Spider (0.5.2)
        - [ ] Facebook Spider (0.5.2)
    - [ ] Agent Message Tunnel (0.5.2)
        - [ ] E-mail Tunnel,A2
        - [ ] Telegram Tunnel,S2
        - [ ] Discord Tunnel,S2
    - [ ] Home IoT Environment (0.5.2), A4
        - [] Compatible Home Assistant (0.5.2), A4
- [ ] Build-in Agents/Apps
    - [ ] Agent: Personal Information Assistant,@photosssa,@lurenpluto , A2
    - [ ] Agent: Bulter Jarvis,@waterflier, A2
    - [ ] App: Personal Station (0.5.2),A4+S4
- [ ] UI
    - [x] CLI UI (aios_shell),@waterflier,S2
    - [ ] Web UI (0.5.2),A4+S4
- [ ] 0.5.1 Integration Test (Senior*3)
    - [x] Workflow -> AI Agent -> AI Agent,@waterflier,S1
    - [ ] Spider -> Pipline -> Knowledge Base,@photosssa,S2
    - [ ] AI Agent <- Functions <- Knowledge Base,@lurenpluto,S2
- [ ] SDK
    - [x] Workflow SDK,@waterflier, A2
    - [ ] AI Environments SDK (0.5.2), A2
    - [ ] Compute Kernel SDK (0.5.2), A2
- [ ] Document (>0.5.2)
    - [ ] System design document, including the design document of each subsystem
    - [ ] Installation/use document for end users
    - [ ] SDK document for developers


The following is the introduction of the adjustment of each component after the current implementation.

# AIOS Kernel

Define some of the important basic concepts of Intelligent Applications running on OpenDAN

## Agent  

Agent is the core concept of the system, created through appropriate LLM, prompt words, and memory. Agents support our vision of a new relationship between humans and computation in the future:
```
Human <-> Agent <-> Compute 
```
Agents form the basis of future intelligent applications. From the user's perspective, the strength of AIOS is primarily determined by "how many agents with different capabilities it has."
The above process has now been implemented. In practice, I found a key issue is that we need to continuously seek the optimal solution. This issue directly relates to how application developers of OpenDAN build intelligent applications, so I think it has a high priority.

### Optimization of system prompts

The goal is to allow Agents to communicate with other Agents (forming a team), call Functions at the right time, and read/write status through the environment at the right time, using prompt words. The existing implementation is usually:

```
When you decide to communicate with a work group, please use : sendmsg(group_name, content).
```

Our optimization direction is:

1. To allow Agents to initiate calls accurately
2. To use as few precious prompt word resources as possible.

If there are already systematic studies in this field, introductions are also welcome!

## Workflow 

Workflow has realized the concept of allowing multiple Agents to play different roles and collaboratively solve complex problems within an organization. It is also the main form of intelligent applications on OpenDAN. Compared to a single Agent, building a team composed of Agents can effectively solve three inherent problems of LLM:

1. The prompt word window will grow, but it will remain limited for a long time.
2. Like humans, Agents trained on different corpora and algorithms will have different personalities and will excel in different roles.
3. The inference results of LLM are uncontrollable, so accuracy cannot be guaranteed. Just like humans make mistakes, the collaboration of multiple Agents is needed to improve accuracy.

The basic framework of Workflow has been completed (which is also the core of version 0.5.1). Following the subsequent SDK documentation, we now have a basic framework for third-party developers to develop applications on OpenDAN.

## AI Environments

Environments provide an abstraction for AI Agents to access the real world. 

Environments include properties, events, methods (Env.Function), and come with natural language descriptions that Agents can understand. This allows AI Agents to understand the current environment and when to access it. For example, an Agent planning a trip needs to understand the real weather conditions at the destination in the future to make the right decisions. This weather condition needs to be provided to the Agent through Environments. 

The events in Environments also provide logic for the autonomous work of Agents. For example, an Agent can track changes in the user's schedule and date, automatically helping the user plan and track the specific itinerary for the day.

### Celender Environment

The system's default environment, which can access the current time, the user's schedule, and the weather information at a specific location. It also contains some important and basic user information, including home address and office address.

#### Compatible with common Celender services. (0.5.2)

- Microsoft Outlook Calendar
- Google Calendar
- Apple Calendar

### Workspace Environment (0.5.2)

A file system-based workspace environment that allows the Agent to read/write files at appropriate times.

## AI Functions

Function is a core concept of AIOS, providing the Agent with descriptions of suitable callable Functions, allowing the Agent to invoke Functions at the right time. Through Functions, the Agent gains "execution power," rather than just being an advisor that only provides suggestions. The Function framework allows third-party developers to develop and publish Functions, supporting Agents and Workflows to have a list of available Functions, through which they can build appropriate prompt words, enabling the Agent to invoke Functions at the right time.

**Under development.**

### Basic AI Functions （0.5.2）

There are already a plethora of basic services in the world, such as querying the weather at a specific location at a specific time, checking hotel prices, or booking plane tickets. The system should separate the definition and implementation of Basic (generic) Functions, allowing Agent developers to implement common scenarios with generic logic. The definition of generic Functions is undoubtedly similar to standard setting work.

 I know that many other projects have done a lot of work in this field, and ChatGPT also has dedicated function support. What we need to do is to find the open standards that are closest to our goals and then integrate them.

## AI BUS

The AI BUS connects various conceptual entities of OpenDAN. For example, if Agent A wants to send a message to another Agent B and wait for the processing result of the message, it can simply use the AI BUS:

```python
resp = await AIBus.send_msg(agentA,agentB,msg)
```

The abstraction of AI BUS allows different Agents to choose suitable physical hosts to run according to the system's needs. This is also why we define AIOS as a "Network OS". All entities registered on the AI BUS can be accessed via the AI BUS interface. As needed, we will also persist the messages in the AI BUS, so that when a distributed system experiences regular failures, it can continue to work after being pulled up again.

The concept of AI BUS has many similarities with traditional MessageQueues.

## Chatsession

Intuitively, ChatSession saves the "chat history". The chat history is currently the natural source of Agent Memory capability.
Determining a ChatSession has three key attributes: Owner, Topic, and Remote. An operation where A sends a message to B and gets B's reply will generate two messages, and save them in two different ChatSessions.

Currently, ChatSession is saved based on sqlite. After the Zone-level D-RDB is set up in the future, it will be migrated to RD-DB.

## Knowlege Base

Provide a unified interface, support switching vector database kernel 
Integrate open source vector database (pay attention to Lience selection) 
When designing the interface, prepare for future access control

**Under development.**

## Personal Models （>0.5.2）

The goal of this subsystem is to support users in training models based on their own data, including subsequent usage, management, deployment, and other operations of the model. In the early stages, invoking this module and adding new models should be operations performed by advanced users. 

It is still uncertain whether this module will be actively used in intelligent applications.

# Frame Services

The implementation offers a range of fundamental services for traditional Network OS. It connects users' devices to the same Zone via the network and provides a unified abstraction for application access. This component serves as a basic framework and computing resource for the operation of intelligent applications on the upper layer. On the lower layer, it connects various types of hardware through different protocols, integrates resources, and offers a unified abstraction for intelligent applications to access.

## Kernel Service (0.5.2)

The Kernel Service implements the System Calls for OpenDAN and provides a "kernel mode" abstraction. In version 0.5.1, since this component is not yet implemented, all code—whether system services or application code—runs in kernel mode. 

In the future, we plan to maintain the system running in this mode for an extended period, as it facilitates debugging.

The Kernel Service is mainly composed of the following component:

### System-Call Interface

Centralizes the provision and management of system call interfaces.

### Name Service

It is the most crucial foundational state service in a cluster (Zone) comprised of all the user's devices. As the core service of the Zone, it provides the most basic guarantee for the availability and reliability of all services within the Zone. When a user needs to restore the Zone from a backup, the Name Service is the first service to be restored.

Its functionality is similar to that of `etcd` but includes a on-chain component. From a deployment standpoint, it needs to be operationally optimized for small clusters made up of consumer-level user devices.

### Node Daemon

It is a foundational service that runs on all devices that join the Zone, responding to essential kernel scheduling commands. It adjusts the services and data running on that particular device.

### ACL Control (>0.5.2)

Another essential foundational service of the kernel, it is responsible for the overall management of permissions related to users, applications, and data. The Runtime Context reads the relevant information and implements proper isolation.

### Contact Manager

From the perspectives of permission control and some early application scenarios, understanding the user's basic interpersonal relationships is an important component of OpenDAN's intelligent permission system. Therefore, we provide a contact management component at the system kernel layer. This component can be considered an upgraded version of the traditional operating system's "User Group" module.

## Runtime Context (0.5.2)

It serves as the runtime container for user-mode code, offering isolation guarantees for user-mode code.

 Depending on the type of service, we offer three different Runtime Contexts. The most commonly used is Docker, followed by virtual machines, and finally, entire physical machines.

## Package System

The Package Manager is a fundamental component of the system for managing Packages. The sub system provides fundamental support for packaging, publishing, downloading, verifying, installing, and loading folders containing required packages under different scenarios. Based on relevant modules, it's easy to build a package management system similar to apt/pip/npm.

The system design has deeply referenced Git and NDN networks. The distinction between client and server is not that important. Through cryptography, it achieves decentralized trustworthy verification. Any client can become an effective repo server through simple configuration.

Based on the Package System, we can implement the publishing, downloading, and installation of extendable foundational entities such as Agents, Functions, and Environments. This enables the creation of an app store on OpenDAN.

**Under development.**

# AI Compute System 

The purpose of designing Compute System is to enable our users to use their computational resources more efficiently. These computational resources can come from devices they own (such as their workstations and gaming laptops), as well as from cloud computing and decentralized computing networks.

[![compute kernel design](./compute_kernel.png)](compute_task.drawio)

The interface of this component is designed from the perspective of the model user rather than the model trainer. The basic form of its interface is:

```python
compute_kernel.do_compute(function_name, model_name,args)
```

## Scheduler

The goal of the Scheduler component is to select an appropriate ComputeNode to run tasks based on the tasks in the task queue and the known status of all ComputeNodes (which may be delayed). In the current version (0.5.1), the implementation of the Scheduler is only to get the system up and running. In the next version (0.5.2), the overall framework for computing resource scheduling needs to be established.

## LLM 

LLM support is the system's most core functionality. OpenDAN requires that there be at least one available LLM computing node in the system. The supported interfaces are as follows:
```
def llm_completion(self,prompt:AgentPrompt,mode_name:Optional[str] = None,max_token:int = 0):
```
In the current era, many teams are working hard to develop new LLMs . We will also actively integrate these LLMs into OpenDAN.

- [x] GPT4 (Cloud)
- [ ] LLaMa2 **Under development.**
- [ ] Claude2 
- [ ] Falcon2
- [ ] MPT-7B
- [ ] Vicuna


## Embeding

Provides computational support for the vectorization of different types of user data. The specific algorithms supported depend on the requirements of the entire pipeline.

***Under development.***

## Txt2img

Generate images based on text descriptions. According to the implementation mode, we can interface with a cloud-based implementation and a local implementation. 

The local implementation will definitely use Stable Diffusion.

***Under development.***

## Img2txt (>0.5.2)

Generate appropriate text descriptions for the specified images.

## Txt2voice  

Generate voice based on specified text, using a selected model (the focus is on personal models), and guided by certain emotional cue words.

***To be developed***

## Voice2txt

Extract text information from a segment of audio (or video) through speech recognition.

***To be developed***

## Language Translate

Translate a segment of text into a specified target language.

Since LLM itself is developed based on the foundation of translation, I am currently considering whether it is necessary to provide a text translation interface within the computing kernel. Following the principle of not adding entities if they are not needed, it can be postponed from development.
***pending***

# Storage System

The file system (state storage) has always been a critical part of operating systems. Its implementation directly impacts the system's reliability and performance. The challenge of this section is how to transfer key technologies that are already mature in traditional cloud computing to clusters composed of consumer-level electronic devices with low operational maintenance, while still maintaining sufficient reliability and performance. The implementation of the subsystems in this section is of limited stability. Therefore, I believe the focus of OpenDAN in the early stages for this section should be on establishing stable interfaces to get the system running as quickly as possible, with independent improvements to be made in the future.

From the standpoint of trade-offs, our priorities are:

- Abandoning continuous consistency guarantees, the system only provides strong assurance for reliability up to "backup points." This means we allow the loss of some newly added data if the system experiences a failure.

- Allowing downtime, considering the consumer-level power supply, a short period of unavailability of the system itself will not have a significant impact. We can stop the service for backup/migration when necessary.

## DFS

Distributed file system, combining the public storage space on all devices to form a highly reliable, highly available file system.

## Object Storage

Distributed object storage, and based on MapObject, it implements trustworthy RootState management.

(MapObject and RootState is a concept from CYFS)

**Under development.**

## D-RDB

Distributed relational database, providing highly reliable and highly available relational database services (mainly used for OLTP - Online Transaction Processing). We do not encourage application developers to use RDB on a large scale; the main reason for offering this component is for compatibility considerations.

***Pending.***

## D-VDB

Distributed vector database, which currently appears to be the core foundational component of the Knowledge Base library.

***Under development.***

# Embeding Piplines

Read appropriate Raw Files and Meta Data from the specified location in the Storage System. After passing through a series of Embedding Pipelines, save the results to the Vector Database as defined by the Knowledge Base.

***Under development.***

# Network Gateway (0.5.2)

Obtain user data by recognizing network data.
The Gateway also provides an external access entrance for the entire system, and access control can be unified.
Provides the bus abstraction in the network operating system (the network cable is the bus), devices within the Zone are recognized by the system as plug-and-play devices, and can be called by applications/Agents

## NDN Client

AI-related models are all quite large, so we offer a download tool based on NDN (Named Data Networking) theory to replace curl. The NDN Client will continue to support new Content-Based protocols in the future, allowing OpenDAN developers to publish large packages more quickly, at lower costs, and more conveniently.

# Build-in Service

The basic functions of the system implemented by "user mode" can be regarded as pre -installed applications of the system.Let the system have basic availability without installing any intelligent applications.
We should build built-in applications for 1,2 early preset scenarios, rather than all possible scenarios.This allows us to run the system faster and allow us to discover the shortcomings of the system faster, so as to improve the system faster.

## Spider

A series of reptiles are provided to help users import their data into the system.

### E-mail Spider

The most basic spider is used to capture user mail data.The main purpose of this is to determine the general data format(include text,image,contact) and location to save the grabbed data.

### Telegram Spider

Allow users to capture their own Telegram chat records and save them in the Knowlege Base

**To be developed.**

### Twitter Spider (0.5.2)

Allows users to scrape their own Twitter data and save it in the Knowledge Base.

### Facebook Spider (0.5.2)

Allows users to scrape their own Facebook data and save it in the Knowledge Base.

## Agent Message Tunnel （0.5.2）

The original ROBOT module, after considering its actual function, was renamed the Agent Message Tunnel.
This is the default function supported by the system. It supports users to configure different message channels for different Agent/Workflow, so that users can interact with Agent/Worflow through existing software/services.From the perspective of product, the goal of this module can use the core function of OpenDAN without installing any new software on the one hand. On the other hand, it also creates a stronger mental model for users: My Agent can registered social account, so that Agent has his own identity in the virtual world.

### E-mail Tunnel

Let Agent have its own email account. After registration, users can interact with Agent through mail.

### Telegram Tunnel

Let Agent have his own Telegram account. After registration, users can interact with Agent through Telegram.

### Discord Tunnel

Let Agent have its own discord account. After registration, users can interact with agent through Discord.

## Home IoT Environment (0.5.2)

We've implemented a significant built-in environment: the Home Environment. Through this environment, the AI Agent can access real-time status of the home via installed IoT devices, including reading temperature and humidity information, accessing security camera data, and controlling smart devices in the home. This allows users to better manage a large number of smart IoT devices through AI technology. For instance, a user can simply tell the Agent, "Richard is coming over to watch a movie this afternoon," and the AI Agent will automatically read the security camera data, recognize Richard upon arrival, turn on the home projector, close the curtains, and turn on the wall lights.

Thanks to LLM's powerful natural language understanding, all we need to do is connect a smart microphone to the Home Environment and configure a simple voice-to-text feature. This makes it easy to implement a privately deployed and very intelligent version of Alexa.

In terms of system design, we use the Home Environment as an intermediary layer, freeing OpenDAN from having to spend energy on dealing with compatibility issues with various existing, complex IoT protocols. This keeps the system simple and makes it easier to expand.

### Compatible Home Assistant

Home Assistant is a well-known, open-source IoT system. We could consider implementing the Home Environment based on the Home Assistant's API.

# Build-in Agents/Apps

Once users have installed OpenDAN, it should have some basic functionalities, even without the installation of any third-party smart applications. These basic functions are provided via built-in Agents/Applications. Built-in applications have two important implications for OpenDAN:

1. They provide a developer's perspective to scrutinize whether our design is reasonable and the application development process is smooth.
2. Through one or two scenarios, OpenDAN can be quickly put into use by real users in a production environment, and these scenarios can serve as a basis for driving system improvements in OpenDAN.

## Agent: Personal Information Assistant

Through interacting with this Agent, users can use natural language to query information that has already been saved in the Knowledge-Base. For example, "Please show me the photos from my meeting with Richard last week." They can also find their information more accurately based on some interactive questions.

***To be developed.***

## Agent: Bulter Jarvis （0.5.2）

The Butler Agent Jarvis can recognize certain special commands. Through these commands, it can communicate with other Agents in the system, check the system's status, and use all the system's functionalities. It can be seen as another entry point to AIOS_Shell.

Another important function of the Jarvis is to create sessions. When a user has many workflows/agents installed on their OpenDAN, they might not know which workflow/agent to talk to in order to solve a problem. I envision the future mode to be: "If you don't know who to turn to, ask the Jarvis." The Jarvis will create or find a suitable session based on a brief conversation with the user, and then guide the user into this session.

Based on these two functions, the Jarvis might be the only "special Agent" that requires custom development among all Agents, and it is a part of the system.

## App: Personal Station （0.5.2）

The Personal Station is a built-in application that provides a graphical user interface for users to interact with the system. It is a web application that can be accessed through a browser. It is also the first application that users will see after installing OpenDAN. It provides a simple interface for users to interact with the system, and it also provides a way for users to install new applications.

The main functions of Personal Station include:

1. Library, with the help of Personal Information Assistant, you can better manage your own photos, videos, music, documents, etc., and share them with friends more effectively. (For example, ask the assistant to share photos from an event, selecting from those you've starred, and distribute them to friends based on the people appearing in the photos.)
2. HomePage, with functions similar to Facebook/Twitter, where you can post content you want to share. You can also open your Agent to friends and family, allowing them to interact with your Agent, discuss schedule arrangements, and query your KnowledgeBase for open content.

Home Station is a mobile-first WebApp.

# UI

## CLI UI (aios_shell)

The system provides the command line UI interface priority, facing developers and early senior users.

## Web UI (0.5.2)

Web UI interface for end users

# 0.5.1 Integration Test (Senior*3)

Can be divided into 3 parts
1.Workflow -> AI Agent -> AI Agent
2.Spider -> Pipline -> Knowledge Base
3.AI Agent <- Functions <- Knowledge Base


# SDK 

## Workflow SDK

The SDK allows developers to expand the new workflow/agent to the system.
At present, the SDK has completed the most original version. In ROOTFS/, the .tmol file is written according to the directory structure, and a new workflow/ agent can be added to the system.

## AI Environments SDK （>0.5.2）

The SDK allows developers to expand the system that can be called by AI, including
- Expand the new environment
- Expand the new function

## Compute Kernel SDK （>0.5.2）

This SDK allows developers to expand more core capabilities to the system

# Document (>0.5.2)

When we release 0.5.3, we must complete at least 3 documents:

1. OpenDan's complete system design document, including the design document of each subsystem.
2. Installation/use document for end users.
3. SDK document for developers.

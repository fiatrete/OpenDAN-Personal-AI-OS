# OpenDAN Quick Start
OpenDAN (Open and Do Anything Now with AI) is revolutionizing the AI landscape with its Personal AI Operating System. Designed for seamless integration of diverse AI modules, it ensures unmatched interoperability. OpenDAN empowers users to craft powerful AI agents—from butlers and assistants to personal tutors and digital companions—all while retaining control. These agents can team up to tackle complex challenges, integrate with existing services, and command smart(IoT) devices. 

With OpenDAN, we're putting AI in your hands, making life simpler and smarter.

This project is still in its very early stages, and there may be significant changes in the future.
## Installation

There are two ways to install the Internal Test Version of OpenDAN:
1. Installation through docker, this is also the installation method we recommend now
2. Installing through the source code, this method may encounter some traditional Pyhont dependence problems and requires you to have a certain ability to solve.But if you want to do secondary development of OpenDAN, this method is necessary.

### Preparation before installation
1. Docker environment
This article does not introduce how to install the docker, execute it under your console
```
docker -version
```
If you can see the docker version number (> 20.0), it means that you have installed Docker.
If you don't know how to install docker, you can refer to [here](https://docs.docker.com/engine/install/)

2. OpenAI API Token
If there is no api token, you can apply for [here](https://beta.openai.com/)
(Applying for the API Token may have some thresholds for new players. You can find friends around you, and you can give you a temporary, or join our internal test experience group. We will also release some free experience API token from time to time.These token is limited to the maximum consumption and effective time)

### Install OpenDAN
After executing the following command, you can install the Docker Image of OpenDAN
```
docker pull paios/aios:latest
```

## Run
The first Run of OpenDAN needs to be initialized. You need to enter some information in the process of initialization. Therefore, when starting the docker, remember to bring the -it parameter.

OpenDAN is your Personal AIOS, so it will generate some important personal data (such as chat history with agent, schedule data, etc.) during its operation. These data will be stored on your local disk. ThereforeWe recommend that you mount the local disk into the container of Docker so that the data can be guaranteed.

```
docker run -v /your/local/myai/:/root/myai --name aios -it paios/aios:latest 
```
In the above command, we also set up a Docker instance for Docker Run named AIOS, which is convenient for subsequent operations.You can also use your favorite name instead

After executing the above command, if everything is normal, you will see the following interface
![image]


After the first operation of the docker instance is created, it only needs to be executed again:
```
docker start -ai aios
```
If you plan to run in a service mode (NO UI), you don't need to bring the -AI parameter:
```
docker start aios
```

## The first run configuration

If you have not used the character interface (CLI) in the past, you may not be used to it.But don't be nervous, even in the Internal Test version, you will only need to use CLI in a few cases.

OpenDAN must be a future operating system that everyone can easily use, so we hope that the use and configuration of OpenDAN are very friendly and simple.But in the Internal Test, we have not enough resources to achieve this goal.After thinking, we decided to support the use of OpenDAN by CLI.

OpenDAN uses LLM as the kernel of AIOS, and integrates many very COOL AI functions through different Agent/Workflow. You can experience some of the latest success of the AI industry in OpenDAN.To activate all the functions requires more configuration, but we only need to do two configurations for the first operation.

1. LLM Kernel

OpenDAN is a future AI Operating Yystem built around LLM, so the system must have `at least one LLM core`.

OpenDan configures LLM in the agent unit. Agent, which does not specify the LLM model name, will use GPT4 by default (GPT4 is also the smartest LLM).You can modify the local LLM that configures to LLaMa or other installed.Today, Local LLM requires the support of quite strong local computing resource, which requires a lot of one-time investment.

But we believe that the LLM field will also follow `Moore's law`. The future LLM model will become more and more powerful, smaller and cheaper.Therefore, we believe that in the future, everyone will have their own Local LLM.

2. Your personal information

This allows your personal AI assistant Jarvis to better serve you. Note that you must enter your own correct Telegram username, otherwise due to authority control, you will not be able to access Agent/Workflow installed on OpenDan through Telegram.

Okay, after a simple understanding of the above background, press the interface to prompt the input of the necessary information.

P.S:
The above configuration will be saved in the `/your/local/myai/etc/system.cfg.toml`, if you want to modify the configuration, you can directly modify this file.If you want to adjust the configuration, you can edit this file directly.


## (Optional) Install the local LLM kernel
For the first time quickly experience OpenDAN, we strongly recommend you to use GPT4. Although he is very slow and expensive, he is also the most powerful and stable LLM core at present.OpenDAN In the architecture design, different agents are allowed to choose different LLM kernels (but at least one available LLM kernel in the system should be available in the system). If you cannot use GPT4 for various reasons, you can use the Local LLM.
At present, we only adapt to LOCAL LLM based on LLaMa.CPP, and use the following method to install

（Coming Soon）

## Hello, Jarvis!
After the configuration is completed, you will enter a AIOS Shell, which is similar to Linux Bash and similar. The meaning of this interface is:
The current user "username" is communicating with the name "Agent/Workflow of Jarvis". The current topic is default.

Say Hello to your private AI assistant Jarvis !

**If everything is OK, you will get a reply from Jarvis after a moment .At this time, the OpenDAN system is running .**

## Give a Telegram account to Jarvis

You've successfully installed and configured OpenDAN, and verified that it's working properly. Now, let's quickly return to the familiar graphical interface, back to the mobile internet world!
We'll be registering a Telegram account for Jarvis. Through Telegram, you can communicate with Jarvis in a way that feels familiar.
In the OpenDAN's aios_shell, type:
```
/connect Jarvis
```
Follow the prompts to input the Telegram Bot Token, and you'll have Jarvis set up. To learn how to obtain a Telegram Bot Token, you can refer to the following article:
https://core.telegram.org/bots#how-do-i-create-a-bot.

Additionally, we offer the option to register an email account for the Agent. Use the following command:
```
/connect Jarvis email
```
Then follow the prompts to link an email account to Jarvis. However, as the current system doesn't have a pre-filter customized for email contents, there's a potential for significant LLM access costs. Hence, email support is experimental. We recommend creating a brand-new email account for the Agent."

## Running OpenDAN as a Service
The method described above runs OpenDAN interactively, which is suitable for development and debugging purposes. For regular use, we recommend running OpenDAN as a service. This ensures OpenDAN operates silently in the background without disturbing your usual tasks.
First, input:
```
/exit
```
to shut down and exit OpenDAN. Then, we'll start OpenDAN as a service using:
```
docker start aios
```
Jarvis, which is an Agent running on OpenDAN, will also be terminated once OpenDAN exits. So, if you wish to communicate with Jarvis via Telegram anytime, anywhere, remember to keep OpenDAN running (don't turn off your computer and maintain an active internet connection).

In fact, OpenDAN is a quintessential Personal OS, operating atop a Personal Server. For a detailed definition of a Personal Server, you can refer to the OOD concept by CYFS at https://www.cyfs.com/. Running on a PC or laptop isn't the formal choice, but then again, aren't we in an Internal Test phase?

Much of our ongoing research and development work aims to provide an easy setup for a Personal Server equipped with AIOS. Compared to a PC, we're coining this new device as PI (Personal Intelligence), with OpenDAN being the premier OS tailored for the PI.

## Introducing Jarvis: Your Personal Butler!
Now you can talk with Jarvis anytime, anywhere via Telegram. However, merely seeing him as a more accessible ChatGPT doesn't do justice to his capabilities. Let's dive in and see what new tricks Jarvis, running on OpenDAN, brings to the table!

## Let Jarvis Plan Your Schedule

Many folks rely on traditional calendar software like Outlook to manage their schedules. I personally spend at least two hours each week using such applications. Manual adjustments to plans, especially unforeseen ones, can be tedious. As your personal butler, Jarvis should effortlessly manage your schedule through natural language!
Try telling Jarvis:
```
I'm going hiking with Alice on Saturday morning and seeing a movie in the afternoon!
```
If everything's in order, you'll see Jarvis' response, and he'll remember your plans.
You can inquire about your plans with Jarvis using natural language, like:
```
What are my plans for this weekend?
```
Jarvis will respond with a list of your scheduled activities.
Since Jarvis uses LLM as its thinking core, he can communicate with you seamlessly, adjusting your schedule when needed. For instance, you can tell him:
```
A friend is coming over from LA on Saturday, and it's been ages since we last met. Shift all of Saturday's appointments to Sunday, please!
```
Jarvis will seamlessly reschedule your Saturday plans for Sunday.
Throughout these interactions, there's no need to consciously use "schedule management language." As your butler, Jarvis understands your personal data and engages at the right moments, helping manage your schedule.
This is a basic yet practical illustration. Through this example, it's clear that people might no longer need to familiarize themselves with foundational software of today.

Welcome to the new era!

All the schedules set by the Agent are stored in the ~/myai/calender.db file, formatted as sqlite DB. In future updates, we plan to authorize Jarvis to access your production environment calendars (like the commonly-used Google Calendar). Still, our hope for the future is that people store vital personal data on a physically-owned Personal Server.

## Introducing Jarvis to Your Friends
Sharing Jarvis's Telegram account with your friends can lead to some interesting interactions. For instance, if they can't get in touch with you directly, they can communicate with Jarvis, your advanced personal assistant, to handle transactional tasks like inquiring about your recent schedules or plans.

After trying, you'll realize that Jarvis doesn't operate as anticipated. From a data privacy standpoint, Jarvis, by default, interacts only with "trusted individuals". To achieve the above objectives, you need to let Jarvis understand your interpersonal relationships.

### Let Jarvis Manage Your Contacts
OpenDAN stores the information of all known individuals in the myai/contacts.toml file. Currently, it's simply divided into two groups:
1. Family Member, At present, this group stores your information (logged during the system's initial setup).
2. Contact，These are typically your friends.

Anyone not listed in the aforementioned categories is classified as a Guest by the system. By default, Jarvis doesn't engage with Guests. Hence, if you want Jarvis to interact with your friends, you must add them to the Contact list.

You can manually edit the myai/contacts.toml file, or you can let Jarvis handle the contact addition. Try telling Jarvis:
```
Please add my friend Alice to my contacts. Her Telegram username is xxxx, and her email is xxxx.
```
Jarvis will comprehend your intent and carry out the task of adding the contact.

Once the contact is added, your friend can interact with your personal butler, Jarvis.


## Agents Can Access Your Information through OpenDAN (Coming soon)
You're now aware that Jarvis can manage essential personal data for you through OpenDAN. However, this data is mainly "new information". Since the invention of the PC in the 1980s, our lives have been increasingly digitized. Each of us has a massive amount of digital data, ranging from photos and videos captured on smartphones to emails and documents from work. In the past, we managed this information using file systems. In the AI era, we will use a Knowledge Base to manage this data. Information entered into the Knowledge Base can be better accessed by AI, allowing your Agent to understand you more deeply, serve you better, and truly become your exclusive personal butler.

The Knowledge Base is a fundamental concept within OpenDAN and a key reason for the need for a Personal AIOS. Knowledge Base technology is rapidly evolving, so the implementation of OpenDAN's Knowledge Base is also swiftly advancing. The current version aims to let users experience the new capabilities brought about by the combination of the Knowledge Base and the Agent. From a system design perspective, we also hope to offer a friendlier and smoother method for users to import existing personal information.

The Knowledge Base feature is already enabled by default. There are two ways to add your data to the Knowledge Base:
1）Copy the data you wish to add to the Knowledge Base to the ~myai/data folder.
2）Use the command /knowledge add $dir to include data from the $dir directory into the Knowledge Base. Note that OpenDAN runs in a container by default, so $dir refers to the path relative to the container. If you wish to add local data, you first need to mount the local data inside the container.

During tests, please avoid adding large files or files with highly sensitive information. OpenDAN will continuously scan the files in this folder in the background and add them to the Knowledge Base. The range of recognizable file formats is currently limited, with supported types including text files, images, short videos, etc.

You can check the scanning task status in the command line using:
```
/knowlege journal
```

### Meet Your Personal Information Assistant, Mia (Coming soon)
Next, you can access the Knowledge Base via the Agent "Mia." Try interacting with Mia!
```
/open Mia
```

Mia is designed to assist you in navigating through your Knowledge Base, allowing you to swiftly retrieve and understand your stored digital information. Think of her as your digital librarian, always ready to help you locate and comprehend your archived data with ease. Whether it's an old document, a treasured photo, or an important email, Mia is here to streamline your digital life.

### (Optional) Enable Local Embedding
The process wherein the Knowledge Base scans and reads files, generating information accessible to the Agent, is termed Embedding. This procedure requires computational resources. Therefore, by default, we utilize OpenAI's Embedding service to execute this task. This implies that files added to the Knowledge Base will be uploaded to OpenAI's services for processing. Although OpenAI currently holds a commendable reputation, there still exists potential risks of privacy breaches. If you possess adequate local computational capabilities (the requirements are significantly lower than Local LLM), we recommend enabling the local Embedding feature to enhance your privacy protection.

（Coming soon）


## bash@ai
By enabling the Agent to execute bash commands, you can also grant OpenDAN quick and easy access to your private data. Use the command:
```
/open ai_bash
```
to activate ai_bash. From there, you can execute traditional bash commands within the aios_shell command line. Plus, you'll have the ability to use smart commands. For example, to search for files, instead of using the 'find' command, you can simply say:
```
Help me find all files in ~/Documents that contain OpenDAN.
```
Pretty cool, right?

By default, OpenDAN operates inside a container, meaning ai_bash can only access files within that docker container. While this provides a relative level of security, we still advise caution. Do not expose the ai_bash agent recklessly, as it could pose potential security risks."

## Why Do We Need Personal AIOS?
Many might immediately think of privacy as the primary concern. While it's a crucial factor, we don't believe it's the real reason people are moving away from ChatGTP and opting for Personal AIOS. After all, most individuals are not overly sensitive to privacy concerns. Moreover, platform providers today usually monetize your private data without openly violating it – there's at least some semblance of integrity there.

We believe:
 
1. Cost is a significant determinant. LLM (Large Language Model) offers potent, well-defined capabilities. It's the new-age CPU. From a product and business perspective, products like ChatGTP only allow effective, constrained usage of this power. It's reminiscent of the early days of minicomputers when systems were time-shared: useful but limited. To truly harness the potential of LLM, we need to ensure that every individual owns their LLM. They should freely utilize the LLM as a foundational component for any application. This necessitates an operating system constructed on the principles of LLM.
2. Once you possess an LLM, you'll realize the vastness of possibilities! The current capabilities of ChatGPT, even with plugins extending LLM's functionalities, are considerably limited. This limitation stems both from commercial considerations and the legal constraints traditional cloud services face. The platforms bear too much responsibility. But, with LLM in AIOS, you can seamlessly integrate natural language, LLM, existing services, and smart devices. You no longer have to fret about privacy breaches or liability concerns – you assume responsibility for the outcomes once you grant access to LLM!

OpenDAN is an open-source project, let's define the future of Humans and AI together!
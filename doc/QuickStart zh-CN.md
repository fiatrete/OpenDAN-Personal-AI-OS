# OpenDAN Quick Start
OpenDAN (Open and Do Anything Now with AI) is revolutionizing the AI landscape with its Personal AI Operating System. Designed for seamless integration of diverse AI modules, it ensures unmatched interoperability. OpenDAN empowers users to craft powerful AI agents—from butlers and assistants to personal tutors and digital companions—all while retaining control. These agents can team up to tackle complex challenges, integrate with existing services, and command smart(IoT) devices. 

With OpenDAN, we're putting AI in your hands, making life simpler and smarter.

This project is still in its very early stages, and there may be significant changes in the future.

## Installation

OpenDAN的internal test版本有两种安装方式：
1.通过Docker安装，这也是我们现在推荐的安装方法
2.通过源代码安装，这种方法可能会遇到一些传统的Python依赖问题，需要你有一定的解决能力。但是如果你想要对OpenDAN进行二次开发，这种方法是必须的。

### 安装前准备工作
1. Docker环境
OpenDAN通过适配Docker实现了对多平台的适配。本文不介绍怎么安装Docker,在你的控制台下执行
```
docker --version
```
如果能够看到Docker的版本号（>20.0），说明你已经安装了Docker.
不知道怎么安装Docker的话，可以参考[这里](https://docs.docker.com/engine/install/)

2. OpenAI的API Token
如果你还没有API Token的话，可以通过[这里](https://beta.openai.com/)申请
（申请API Token对新玩家可能有一些门槛，可以在身边找找朋友，可以让他们给你一个临时的，或则加入我们的内测体验群，我们也会不时放出一些免费体验的API Token,这些Token被限制了最大消费和有效时间）

#### 安装OpenDAN
执行下面的命令，就可以安装OpenDAN的Docker Image了
```
docker pull paios/aios:latest
```

## 运行OpenDAN
首次运行OpenDAN需要进行初始化，初始化过程中需要你输入一些信息，因此启动Docker的时候记住要带上 -it参数。
OpenDAN是你的Personal AIOS,因此其运行过程中会产生一些重要的个人数据（比如和Agent的对话记录，日程数据等），这些数据会保存在你的本地磁盘上，因此在启动Docker的时候，我们推荐你将本地磁盘挂载到Docker的容器中，这样才能保证数据的持久化。

```
docker run -v /your/local/myai/:/root/myai --name aios -it paios/aios:latest 
```
在上述命令中，我们还为docker run创建的docker 实例起了一个名字叫aios,方便后续的操作。你也可以用自己喜欢的名字来代替

执行上述命令后，如果一切正常，你会看到如下界面
![image]


首次运行完成Docker实例的创建后，再次运行只需要执行：
```
docker start -ai aios
```

如果打算以服务模式运行，则不用带 -ai参数：
```
docker start aios
```

## OpenDAN的首次运行配置

如果你过去没有用字符界面(CLI)的产品，可能会有一点点不习惯。但别紧张，即使在Internal Test版本中，你也只会在极少数的情况下需要使用CLI。

OpenDAN必须是所有人都能轻松使用的未来操作系统，因此我们希望OpenDAN的使用和配置都是非常友好和简单的。但在Internal Test版本中，我们还没有足够的资源来实现这一目标。经过思考，我们决定先支持以CLI的方式来使用OpenDAN。

OpenDAN以LLM为AIOS的内核，通过不同的Agent/Workflow整合了很多很Cool的AI功能，你能在OpenDAN里一站式的体验AI工业的一些最新的成功。激活全部的功能需要做比较多的配置，但首次运行我们只需要做两项配置就可以了
1. LLM内核。OpenDAN是围绕LLM构建的未来智能操作系统，因此系统必须有至少一个LLM内核。
    OpenDAN以Agent为单位对LLM进行配置，未指定LLM模型名的Agent将会默认使用GPT4（GPT4也是目前最聪明的LLM）。你可以修改该配置到llama或其它安装的Local LLM。今天使用Local LLM需要相当强的本地算力的支持，这需要一笔不小的一次性投入。
    但我们相信LLM领域也会遵循摩尔定律，未来的LLM模型会越来越强大，越来越小，越来越便宜。因此我们相信在未来，每个人都会有自己的Local LLM。
2. 你的个人信息，这能让你的私人AI管家Jarvis更好的为你服务。注意这里一定要输入你自己正确的Telegram username ,否则由于权限控制，后续将无法通过Telegram访问OpenDAN上安装的Agent/Workflow。

好的，简单的了解了上述背景后，请按界面提示完成必要信息的输入。

P.S:
上述配置会保存在`/your/local/myai/etc/system.cfg.toml`中，如果你想要修改配置，可以直接修改这个文件。如果你想要调整配置，可以直接编辑这个文件。


## （可选）安装本地LLM内核
首次快速体验OpenDAN,我们强烈的推荐你使用GPT4，虽然它很慢，也很贵，但它也是目前最强大和稳定的LLM内核。OpenDAN在架构设计上，允许不同的Agent选择不同的LLM内核（但系统里至少要有一个可用的LLM内核），如果你因为各种原因无法使用GPT4，可以是用下面方法安装Local LLM.
目前我们只适配了基于Llama.cpp的Local LLM，用下面方法安装

### 安装LLaMa ComputeNode
OpenDAN支持分布式计算资源调度，因此你可以把LLaMa的计算节点安装在不同的机器上。在本地运行LLaMa根据模型的大小需要相当的算力支持，请根据自己的机器配置量力而行。我们使用llama.cpp构建LLaMa LLM ComputeNode,llama.cpp也是一个正在高速演化的项目，请阅读llamap.cpp的项目

## Hello, Jarvis!
配置完成后，你会进入一个AIOS Shell,这和linux bash 和相似，这个界面的含义是：
当前用户 "username" 正在 和 名“为Jarvis的Agent/Workflow” 进行交流，当前话题是default。
和你的私人AI管家Jarvis Say Hello吧！

*** 如果一切正常，你将会在一小会后得到Jarvis的回复。此时OpenDAN系统已经正常运行了。***

## 给Jarvis注册Telegram账号
你已经完成了OpenDAN的安装和配置，并已经验证了其可以正常工作。下面让我们尽快回到熟悉的图形界面，回到移动互联网吧！
我们将给Jarvis注册一个Telegram账号，通过Telegram，我们可以使用熟悉的方式和Jarvis进行交流了~
在OpenDAN的aios_shell输入
```
/connect Jarvis
```
按照提示输入Telegram Bot Token就完成了Jarvis的账号注册. 你可以通过阅读下面文章来了解如何获取Telegram Bot Token
https://core.telegram.org/bots#how-do-i-create-a-bot，

我们还支持给Agent注册email账号，用下面命令行
```
/connect Jarvis email
```
然后根据提示就可以给Jarvis绑定电子邮件账号了。但由于目前系统并未对email内容定制前置过滤，所以可能会带来潜在的大量LLM访问费用，因此Email的支持是实验性的。我们推荐给Agent创建全新的电子邮件账号。


## 以服务方式运行OpenDAN
上述的运行方式是以交互方式运行OpenDAN，这种方式适合在开发和调试的时候使用。在实际使用的时候，我们推荐以服务方式运行OpenDAN，这样可以让OpenDAN在后台默默的运行，不会影响你的正常使用。
先输入
```
/exit
```
关闭并退出OpenDAN,随后我们再用服务的方式启动OpenDAN：
```
docker start aios
```

Jarvis是运行在OpenDAN上的Agent,当OpenDAN退出后，其活动也会被终止。因此如果想随时随地通过Telegram和Jarvis交流，请记住保持OpenDAN的运行（不要关闭你的电脑，并保持其网络连接）。

实际上,OpenDAN是一个典型的Personal OS，运行在Personal Server之上。关于Personal Servier的详细定义可以参考CYFS（https://www.cyfs.com/）的OOD构想。因此运行在PC或笔记本上并不是一个正式选择，但谁要我们正在Internal Test呢？

我们正在进行的很多研发工作，其中有很大一部分的目标，就是能让你轻松的拥有一个搭载AIOS的Personal Server.相对PC，我们将把这个新设备叫PI(Personal Intelligence)，OpenDAN是面向PI的首个OS。

## 更新OpenDAN的镜像
现在OpenDAN还处在早期阶段，因此我们会定期更新OpenDAN的镜像，因此你可能需要定期更新你的OpenDAN镜像。更新OpenDAN的镜像非常简单，只需要执行下面的命令就可以了
```
docker stop aios
docker rm aios
docker pull paios/aios:latest
docker run -v /your/local/myai/:/root/myai --name aios -it paios/aios:latest 
```


## 你的私人管家 Jarvis 前来报道！
现在你已经可以随时随地通过Telegram和Jarvis交流了，但只是把他看成更易于访问的ChatGPT,未免有点小瞧他了。让我们来看一下运行在OpenDAN里的Jarvis有什么新本事吧！

## 让Jarvis给你安排日程

相信不少朋友有长期使用Outlook等传统Calender软件来管理自己日程的习惯。像我自己通常每周会花至少2个小时来是使用这类软件，当发生一些计划外的情况时，对计划进行手工调整是一个枯燥的工作。作为你的私人管家，Jarvis必须能够帮用自然语言的方式帮你管理日程！
试试和Jarvis说：
```
我周六和Alic上午去爬山，下午去看电影！
```
如果一切正常，你会看到Jarvis的回复，并且已经记住了你的日程安排。
你可以通过自然语言的方式和Jarvis查询
```
我这周末有哪些安排？
```
你会看到Jarvis的回复，其中包含了你的日程安排。
由于Jarvis使用LLM作为思考内核，他能以非常自然的方式和你进行交流，并在合适的时候管理你的日程。比如你可以说
```
我周六有朋友从LA过来，很久没见了，所有周六的约会都移动到周日吧！
```
你会看到Jarvis会自动的帮你吧周六的日程移动到周日。
实际上在整个交流的过程中，你不需要有明确的“使用日程管理语言的意识”，Jarvis作为你的管家，在理解你的个人数据的基础上，会在合适的时机和你进行交流，帮你管理日程。
这是一个非常简单而又常用的例子，通过这个例子，我们可以看到未来人们不再需要学习一些今天非常重要的基础软件了。

欢迎来到新时代！

Agent安排的日程数据都保存在 ~/myai/calender.db 文件中，格式是sqlite DB. 我们后续计划授权让Jarvis可以操作你生产环境中的Calender(比如常用的Google Calender)。但我们还是希望未来，人们可以把重要的个人数据都保存在自己物理上拥有的Personal Server中。

## 介绍Jarvis给你的朋友
把Jarvis的telegram账号分享给你的朋友，可以做一些有趣的事情。比如你的朋友可以在联系不到你的时候，通过Jarvis，你的高级私人助理来处理一些事务性的工作，比如了解你最近的日程安排或计划。
尝试后你会发现，Jarvis并不会按预期工作。是因为站在数据隐私的角度，Jarvis默认只会和“可信的人”进行交流。要实现上面目标，你需要让Jarvis能了解你的人际关系。

### 让Jarvis管理你的联系人
openDAN在 myai/contacts.toml 文件中保存了系统已知的所有人的信息。现在非常简单的分成了两组
1. Family Member,现在该文件里保存里你自己的信息（在系统首次初始化时登陆的）添加
2. Contact，通常是你的好友

任何不存在上述列表中的联系人，都会被系统划分到`Guest`。Jarvis默认不允许和`Guest`进行交流。因此如果你想要让Jarvis和你的朋友进行交流，你需要把他添加到`Contact`中。
你可以手工修改 myai/contacts.toml 文件，也可以通过Jarvis来添加联系人。试试和Jarvis说
```
Jarvis,请添加我的朋友Alic到我的联系人中，他的telegram username是xxxx,email是xxxx
```
Jarvis能够理解你的意图，并完成添加联系人的工作。
添加联系人后，你的朋友就可以和你的私人管家Jarvis进行交流了。


## Agent可以通过OpenDAN进一步访问你的信息 （Coming soon）
你已经知道Jarvis可以通过OpenDAN帮你管理一些重要的个人信息。但这些信息都是“新增信息”。在上世纪80年代PC发明以后，我们的一切都在高速的数字化。每个人都有海量的数字信息，包括你通过智能手机拍摄的照片，视频，你工作中产生的邮件文档等等。过去我们通过文件系统来管理这些信息，在AI时代，我们将通过Knowledge Base来管理这些信息，进入Knowlege Base的信息能更好的被AI访问，让你的Agent更理解你，更好的为你服务，真正成为你的专属私人管家。

Knowlege Base是OpenDAN里非常重要的一个基础概念，也是我们为什么需要Personal AIOS的一个关键原因。Knowlege Base相关的技术目前正在快速发展，因此OpenDAN的Knowlege Base的实现也在快速的进化。目前版本的效果更多的是让大家能体验Knowlege Base与Agent结合带来的新能力。站在系统设计的角度，我们也希望能提供一个对用户更友好，更平滑的方法来把已经存在的个人信息导入。

Knowlege Base功能已经默认开启了，将自己的数据放入Knowlege Base有两种方法
1）把要放入KnowlegeBase的数据复制到 `~myai/data`` 文件夹中
2）通过输入`/knowlege add $dir` 将$dir目录下的数据加入到Knowlege Base中，注意OpenDAN默认运行在容器中，因此$dir是相对于容器的路径，如果你想要加入本地的数据，需要先把本地数据挂载到容器中。

测试时请不要放大量文件，或有非常敏感信息的文件。OpenDAN会在后台不断扫描该文件夹中的文件并加入到Knowlege Base中。
目前能识别的文件格式有限，我们支持的文件类型有文本文件、图片、短视频等。

可以在命令行中通过
```
/knowlege journal
```
来查询扫描任务的状态。

### 认识你的个人信息助手Mia
然后我们可以通过 Agent "Mia"来访问Knwolege Base,试着与Mia交流一下吧！
```
/open Mia
```


### (可选)启用本地Embeding
Knowlege Base扫描并读取文件，产生Agent可以访问的信息的过程被称作Embeding.这个过程需要一定的计算资源，因此我们默认使用OpenAI的Embeding服务来完成这个工作。`这意味着加入Knowlege Base的文件会被上传到OpenAI的服务进行处理`，虽然OpenAI的信誉现在不错，但这依旧有潜在的隐私泄露风险。如果你有足够的本地算力（这个要求比Local LLM低很多），我们推荐你在本地启用Embeding的功能，更好的保护自己的隐私

（Coming soon）


## bash@aios
通过让Agent可以执行bash命令，也可以非常简单快速的让OpenDAN具有你的私有数据的访问能力。
使用命令
```
/open ai_bash
```
打开ai_bash,然后你就可以在aios_shell的命令行中执行传统的bash命令了。同时你还拥有了智能命令的能力，比如查找文件，你可以用
```
帮我查找 ~/Documents 目录下所有包含OpenDAN的文件
```
来代替输入find命令~ 非常酷吧！

OpenDAN目前默认运行在容器中，因此ai_bash也只能访问docker容器中的文件。这相对安全，但我们还是提醒你不要轻易的把ai_bash这个agent暴露出去，可能会带来潜在的安全风险。




## 我们为什么需要Personal AIOS?
很多人会第一个想到隐私，这是一个重要的原因，但我们不认为这是人们真正离开ChatGPT,选择Personal AIOS的真正原因。毕竟大部分人并不对隐私敏感。而且今天的平台厂商一般都是默默的使用你的隐私赚钱，而很少会真正泄露你的隐私，还算有一点道义。

我们认为:   
1）成本是一个重要的决定因素。LLM是非常强大的，边界非常清楚的功能。是新时代的CPU。从产品和商业的角度，ChatGPT类产品只允许用有效的方法来使用它。让我想起了小型机刚刚出现时大家分时使用系统的时代：有用，但有限。要真正发挥LLM的价值，我们需要让每个人都能拥有自己的LLM，并能自由的使用LLM作为任何应用的底层组件，这就必须要通过一个基于LLM理论构建的操作系统来使用。
2）当拥有LLM后，你发现能做到的事情太多了！现在的ChatGPT通过Plugin对LLM能力的扩展，其能力边界是非常有限的，这里既有商业成本的原因，也有传统云服务的法律边界问题：平台要承担的责任太多了。而通过在AIOS中使用LLM，你可以自由的把自然语言，LLM，已有服务，智能设备连接在一起，并不用担心隐私泄露和责任问题（你自己承担了授权给LLM后产生后果的责任）！

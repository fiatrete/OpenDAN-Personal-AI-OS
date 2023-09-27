# OpenDAN : Your Personal AIOS
(说明我们的愿景)

OpenDAN的internal test版本有两种安装方式：
1.通过Docker安装，这也是我们现在推荐的安装方法
2.通过源代码安装，这种方法可能会遇到一些传统的Pyhont依赖问题，需要你有一定的解决能力。但是如果你想要对OpenDAN进行二次开发，这种方法是必须的。

# 安装前准备工作
1. Docker环境
本文不介绍怎么安装Docker,在你的控制台下执行
```
docker --version
```
如果能够看到Docker的版本号（>20.10），说明你已经安装了Docker.
不知道怎么安装Docker的话，可以参考[这里](https://docs.docker.com/engine/install/)

2. OpenAI的API Token
还没有API Token的话，可以通过[这里](https://beta.openai.com/)申请
（申请API Token对新玩家可能有一些门槛，可以在身边找找朋友，可以让他们给你一个临时的，或则加入我们的内测体验群，我们也会不时放出一些免费体验的API Token,这些Token被限制在了月均消费$5）

# 安装OpenDAN
```
docker pull paios/aios:latest
```

# 运行OpenDAN
首次运行OpenDAN需要进行初始化，初始化过程中需要你输入一些信息，因此启动Docker的时候记住要带上 -it参数。
OpenDAN时你的Personal AIOS,因此其运行过程中会产生一些重要的个人数据（比如对话记录，日程数据等），这些数据会保存在你的本地磁盘上，因此在启动Docker的时候，我们推荐你将本地磁盘挂载到Docker的容器中，这样才能保证数据的持久化。

```
docker run -v /your/local/myai/:/root/myai --name aios -it paios/aios:latest 
```

执行上述命令后，如果一切正常，你会看到如下界面
![image](https://user-images.githubusercontent.com/11796024/120933872-0b8b6b00-c72a-11eb-9b0b-3b0b8b8b0b0b.png)

后续运行
```
docker start -ai aios
```
以服务模式
```
docker start aios
```

# OpenDAN的首次运行配置

如果你过去没有用过CLI的产品，可能会有一点点不习惯，但别紧张，即使在Internal Test版本中，你也只会在极少数的情况下需要使用CLI。
OpenDAN必须是所有人都能轻松使用的未来操作系统，因此我们希望OpenDAN的使用和配置都是非常友好和简单的。但在Internal Test版本中，我们还没有足够的资源来实现这一目标。经过思考，我们决定先支持CLI的方式来使用OpenDAN。

OpenDAN以LLM为AIOS的内核，通过不同的Agent/Workflow整合了很多很Cool的AI功能，你可以在OpenDAN里一站式的体验AI工业的一些最新的功能。激活全部的功能需要做比较多的配置，但首次运行我们只需要做两项配置就可以了
1. LLM内核。OpenDAN是围绕LLM构建的未来智能操作系统，因此系统必须有至少一个LLM内核。
    OpenDAN以Agent为单位对LLM进行配置，未指定LLM模型名的Agent将会默认使用GPT4（GPT4也是目前最聪明的LLM）。你可以修改该配置到llama或其它安装的Local LLM。今天使用Local LLM需要相当强的本地算力的支持，这需要一笔不小的一次性投入。
    但我们相信LLM领域也会遵循摩尔定律，未来的LLM模型会越来越强大，越来越小，越来越便宜。因此我们相信在未来，每个人都会有自己的Local LLM。
2. 你的个人信息，这能让你的私人AI管家Jarvis更好的为你服务。注意这里一定要输入你自己正确的Telegram username ,否则由于系统权限控制，你讲无法通过Telegram访问Agent/Workflow。

好的，简单的了解了上述背景后，请按界面提示完成必要信息的输入。

P.S:
上述配置会保存在`/your/local/myai/etc/system.cfg.toml`中，如果你想要修改配置，可以直接修改这个文件。如果你想要调整配置，可以直接编辑这个文件。


## （可选）安装本地LLM内核
首次快速体验OpenDAN,我们强烈的推荐你使用GPT4，虽然他很慢，也很贵，但他也是目前最强大和稳定的LLM内核。OpenDAN在架构设计上，允许不同的Agent选择不同的LLM内核（但系统里至少要有一个可用的LLM内核），如果你因为各种原因无法使用GPT4，可以是用下面方法安装Local LLM.
目前我们只适配了基于Llama.cpp的Local LLM，用下面方法安装
Step0 检查系统要求
从效果和性能角度，我们适配了13B和70B的两个版本的模型，经过测试，安装这两个模型需要的系统要求如下（给出参考链接）
简单的说，我们的推荐如下：


OpenDAN也是一个NetworkOS，允许系统通过网络访问需要的计算资源。因此Local LLM并不要求和OpenDAN运行在同一个机器上。你可以在局域网中找一台符合上述配置要求的主机来安装Local LLM Compute Node.

Step1 安装LLampa.cpp的Local LLM CopmuteNode Docker Image
```
```
如果Local LLM Compute Node未安装在本机，还要记得打开必要的端口，以便OpenDAN可以访问Local LLM Compute Node.

Step2 配置OpenDAN使用Local LLM
使用命令:
```

```
然后按照提示输入你的Local LLM的URL信息：
完成配置。



## （可选） 配置系统的Socks5代理
OpenDAN也支持socks5代理，对于网络环境不允许直接访问Telegram，GPT4的朋友，可以使用这个配置要求OpenDAN通过代理访问网络。

# Hello, Jarvis!
配置完成后，你会进入一个和bash很类似的界面，这个界面的含义是：
当前用户 "username" 正在 和 名为Jarvis的Agent/Workflow 进行交流，当前话题是default
和你的私人AI管家Jarvis Say Hi吧！
*** 如果一切正常，你将会在一小会后得到Jarvis的回复。此时OpenDAN系统已经正常运行了。***

# 给Jarvis注册Telegram账号
你已经完成了OpenDAN的安装和配置，并已经验证了其可以正常工作。下面让我们回到熟悉的图形界面，回到移动互联网吧！
下面我们将给Jarvis注册一个Telegram账号，通过Telegram，我们可以使用熟悉的方式和Jarvis进行交流了~
在opendan的aios_shell输入
```
/connect Jarvis
```
按照提示输入Telegram Bot Token就完成了Jarvis的账号注册.

P.S 我们还支持给Agent注册email账号，但由于email账户的配置比较复杂，由于篇幅问题本文就先跳过了。有需要的朋友可以手工打开 ~/myai/etc/tunnels.cfg.toml 文件，按文件格式和下面的例子，为Agent添加email账号。
```

```

# 以服务方式运行OpenDAN
上述的运行方式是以交互方式运行OpenDAN，这种方式适合在开发和调试的时候使用。在实际使用的时候，我们推荐以服务方式运行OpenDAN，这样可以让OpenDAN在后台默默的运行，不会影响你的正常使用。
先输入
```
/exit
```
关闭并退出OpenDAN,随后我们再用服务的方式启动OpenDAN：

```
docker run -d opendan/aios:latest -v /your/local/myai/:/root/myai
```

Jarvis是运行在OpenDAN上的Agent,当OpenDAN退出后，其活动也会被终止。因此如果想随时随地通过Telegram和Jarvis交流，请记住保持OpenDAN的运行（不要关闭你的电脑，并保持其网络连接）。
实际上,OpenDAN是一个典型的Person AI OS，运行在Persona OS上（关于Personal OS的定义可以参考OOD的设计）。因此运行在PC或笔记本上并不是一个正式选择，但谁要我们正在Internal Test呢？
我们正在进行的很多研发工作，其中有很大一部分的目标，就是能让你轻松的拥有一个搭载AIOS的Personal Server.相对PC，我们将把这个新设备叫PI()，OpenDAN是面向PI的首个OS。


# 你的私人管家 Jarvis 前来报道！
现在你已经可以随时随地通过Telegram和Jarvis交流了，但只是把他看成更易于访问的ChatGPT,未免有点小瞧他了。让我们来看一下运行在OpenDAN里的Jarvis有什么新本事吧！

## 让Jarvis给你安排日程
(一张图片)

相信有不少朋友有长期使用Outlook等传统Calender软件来管理自己日程的习惯。像我自己通常每周会花至少2个小时来是使用这类软件，当发生一些计划外的情况时，对计划进行调整是一个枯燥的工作。作为你的私人管家，Jarvis必须能够帮用自然语言的方式帮你管理日程！
试试和Jarvis说：
```
我周六和Alick上午去爬山，下午去看电影！
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
这是一个非常简单而又常用的例子，通过这个例子，我们可以看到未来人们不再需要学习一些今天非常重要的基础软件了，欢迎来到新时代！

上述安排的日程数据都保存在 myai/calender.db 文件中，格式是sqlite DB. 我们后续计划授权让Jarvis可以操作你生产环境中的Calender(比如常用的Google Calender)。但我们还是希望未来，人们可以把重要的个人数据都保存在自己物理上拥有的Personal Server中。

## 介绍Jarvis给你的朋友
把Jarvis的telegram账号分享给你的朋友，可以做一些有趣的事情。比如你的朋友可以在联系不到你的时候，通过Jarvis，你的高级私人助理来处理一些事务性的工作，比如了解你最近的日程安排或计划。
尝试后你会发现，Jarvis并不会按预期工作。是因为站在数据隐私的角度，Jarvis默认只会和“可信的人”进行交流。要实现上面目标，你需要让Jarvis能了解你的人际关系。
## 让Jarvis管理你的联系人
openDAN在 myai/contacts.toml 文件中保存了系统已知的所有人的信息。现在非常简单的分成了两组
1. Family Member,现在该文件里保存里你自己的信息（在系统首次初始化时登陆的）添加
2. Contact，通常是你的好友

任何不存在上述列表中的联系人，都会被系统划分到`Guest`。Jarvis默认只会和`Family Member`和`Contact`进行交流。因此如果你想要让Jarvis和你的朋友进行交流，你需要把他添加到`Contact`中。
你可以手工修改 myai/contacts.toml 文件，也可以通过Jarvis来添加联系人。试试和Jarvis说
```
Jarvis,请添加我的朋友Alick到我的联系人中，他的telegram username是xxxx,email是xxxx
```
Jarvis能够理解你的意图，并完成添加联系人的工作。
添加联系人后，你的朋友就可以和你的私人管家Jarvis进行交流了。

## 让Jarvis会推进更专业的Agent来更好的解决特定问题
讲解Agent的概念，再讲一讲Jarvis是什么


# Agent可以通过OpenDAN进一步访问你的信息
你已经知道Jarvis可以通过OpenDAN帮你管理一些重要的个人信息。但这些信息都是“新增信息”。在上世纪80年代PC发明以后，我们的一切都在高数的数字化。每个人都有海量的数字信息，包括你通过智能手机拍摄的照片，视频，你工作中产生的邮件文档等等。过去我们通过文件系统来管理这些信息，在AI时代，我们将通过Knowledge Base来管理这些信息，进入Knowlege Base的信息能更好的被AI访问，让你的Agent更理解你，更好的为你服务，真正成为你的专属私人管家。

Knowlege Base是OpenDAN里非常重要的一个基础概念，也是我们为什么需要Personal AIOS的一个关键原因。Knowlege Base相关的技术目前正在快速发展，因此OpenDAN现在的Knowlege Base的实现也在快速的进化。目前版本的效果更多的是让大家能体验Knowlege Base与Agent结合带来的新能力。站在系统设计的角度，我们也希望能提供一个对用户更友好，更平滑的方法来把已经存在的个人信息导入。

启用Knowlege Base的方法很简单:在aios_shell中输入 (我们又回到了命令行，在下一个版本我们会让Jarvis有能力准确的修改OpenDAN的所有配置)
```
```
完成上述配置后，再把需要加入Knowlege Base的的个人文件复制到该文件就可以了（测试时请不要放大量文件，或有非常敏感信息的文件）。OpenDAN会在后台不断扫描该文件夹中的文件并加入到Knowlege Base中。
目前能识别的文件格式有限，我们支持的文件类型有：



可以在命令行中通过
```
```
来查询扫描任务的状态。
然后我们可以通过 Agent "Mia"来访问Knwolege Base,试着与Mia交流一下吧！
```
```

Jarvis也拥有访问Knowlege Base的能力，只要打开Jarvis的KB权限即可。不过考虑到Jarvis通常会被授权给你的朋友使用，因此我们默认不开放Jarvis的KB权限。如果你想要让Jarvis能访问你的KB，可以通过命令行来修改Jarvis的权限配置。
```
```
（一些更高级的例子演示）


## (可选)启用本地Embeding
Knowlege Base读取文件，产生Agent可以访问的信息的过程被称作Embeding.这个过程需要一定的计算资源，因此我们默认使用OpenAI的Embeding服务来完成这个工作。这意味着加入Knowlege Base的文件会上传到OpenAI的服务进行处理，虽然OpenAI的信誉现在不错，但这依旧有潜在的隐私泄露风险。如果你有足够的本地算力（这个要求比Local LLM低很多），我们推荐你在本地大启用Embeding的功能，更好的保护自己的隐私

（本地embeding启用的方法）


# bash@aios
我们先来体会一下ENV：bash,能阅读本地文件系统的内容（注意安全风险，我们现在Docker里演示是安全的。），要在Docker里预先放一些适合体验的功
bash以文件系统的方式组织文件，因此LLM已经具备了一定的技能去查找和访问文件



# 我们为什么需要Personal AIOS?
很多人会第一个想到隐私，但其实大部分人都是
成本是另一个重要的因素，现在的感觉，让我想起了分时使用系统的时代。
拥有LLM能做到的事情太多了，组合型才是最重要的！
我们有完整的顶层设计！

OpenDAN不是一个实验室产品

# 第二章：OpenDAN的高级功能

# 使用Workflow
讲解原理后，演示Story Maker

# 启用自己的AIGC计算节点

# 训练和使用自己的私有AIGC模型
0.5.2版本

# 第三章：开发运行在OpenDAN上的Agent/Workflow
操作系统最重要的是什么？是定义了一种新应用的形态
OpenDAN现在虽然依然处于早期阶段，但我们对OpenDAN上的应用形态的思考已经基本成型，作为开发者，基于OpenDAN主要有下面几个方向
1. 开发运行在OpenDAN上的Agent
2. 开发运行在OpenDAN上的Workflow
3. 开发可以被Agent访问的Envirnment
4. 发布自己训练的各种模型
5. 支持更多的Tunnel,提高Agent的可访问性
6. 在Personal Server上开发传统的dApp

在系统的内核层面，主要有
1. LLM内核改进
2. 持续改进Knowlege Base：支持更多的文件类型，更好的内容分析能力和知识图谱组织能力，让LLM能更好的理解和访问你的个人信息
3. AI计算引擎，集成更多的AIGC能力 （text_to_video,text_to_3d）

  

# 以开发者模式安装并运行 OpenDAN


# 开发自己的首个Agent并发布




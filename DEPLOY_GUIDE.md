# 奖学金分发系统 DApp · Render 云端部署指南

> 面向对象：区块链零基础、第一次部署到云平台的同学
> 目标：把后端 + 前端部署到 **Render 免费套餐**，拿到一个公网 URL，评委点开就能访问
> 项目目录：`D:\Documents\qwen-agent\ajBjhW5orS\default\SC6113-ScholarshipDApp`
>
> 代码层的适配（Procfile、render.yaml、端口、生产服务器、降级保护）我已经改好并实测通过，你**不用再改任何源码**。本指南只教你在 GitHub / Render / Remix / 水龙头 这些网站上的操作。

---

## 第 0 章：先搞懂 —— Render 部署和本地 demo 是两回事

这是最重要的一章，不理解就会全程懵。

### 0.1 两套环境的区别

| | 本地 demo（第 4-5 章那份） | Render 部署（本指南） |
|---|---|---|
| 链跑在哪 | 你电脑上的本地测试链（8545） | **真正的 Sepolia 公网测试链** |
| 后端跑在哪 | 你电脑（localhost:5000） | Render 云服务器 |
| 谁能访问 | 只有你自己 | 任何人，凭公网 URL |
| 合约地址 | 本地链上的地址 | **必须重新部署到 Sepolia，拿新地址** |
| 数据持久吗 | 链一重启就清空 | Sepolia 是公网，合约永久在链上 |

### 0.2 为什么 Render 上不能用本地链

Render 的服务器在云端（比如新加坡机房），它要连链时，会去连你配置的 `RPC_URL`。你本地的 `http://127.0.0.1:8545` 对 Render 服务器来说，指的是**它自己**，不是你的电脑。所以：

> **Render 上的后端只能连公网能访问的链 —— 也就是 Sepolia。**

这意味着三件事：

1. 合约要**真的部署到 Sepolia**（用 Remix，第 2 章）
2. 你的 MetaMask 要有 **Sepolia 测试币**（第 1 章领）
3. Render 后端的环境变量要填 **Sepolia 合约地址 + 公共 RPC**（第 4 章）

### 0.3 一个必须知道的现实：评委能做什么、不能做什么

部署成功后，评委打开你的公网 URL：

- ✅ **能**：看到页面正常加载、看到 Sepolia 链上的真实奖学金项目列表、看到交易历史
- ⚠️ **要操作（申请/领取）才能**：评委自己的浏览器也得装 MetaMask、切到 Sepolia、还得有 Sepolia 测试币 —— 一般评委不会做这些

所以 **Render 部署的意义是"证明系统能上云、公网可访问、能读到真实链上数据"**，完整的签名交易演示还是靠你本地录的 demo 视频。两者是互补的，作业要求里 `Deployment: Render or AWS` 和 demo 是两项不同的交付。

### 0.4 免费套餐的限制（提前知道，别被吓到）

我查了 Render 2026 年的官方文档，免费版：

- **闲置 15 分钟自动休眠**，下次访问要等约 1 分钟冷启动（会显示一个加载页）
- 每月 750 免费实例小时（够一个服务跑满一个月）
- **文件系统是临时的**：SQLite 数据库每次重启/重新部署都会丢

> 数据库丢了**不影响**你：本项目数据以链上为准，SQLite 只是缓存，重启后会自动从 Sepolia 重新同步。这个设计正好适配 Render 免费版。

---

## 第 1 章：前置准备（约 15 分钟，大部分是等）

### 1.1 确认你有这些账号

| 账号 | 用途 | 没有怎么办 |
|---|---|---|
| **GitHub** | 存代码，Render 从这里拉 | 去 github.com 注册（免费） |
| **Render** | 云平台 | 去 render.com 用 GitHub 账号直接登录（免费，**Web 服务不需要绑信用卡**） |
| **Google 账号** | 领 Sepolia 测试币 | 大概率你已经有 |

### 1.2 领 Sepolia 测试币（关键前置）

你的 MetaMask 现在没有 Sepolia 测试币。部署合约、创建项目、学生申请领取，每一步都要花 gas，没币就动不了。

**好消息**：我刚查了 Sepolia 当前 gas 价格，低到几乎免费（约 1 gwei 甚至更低）。**部署合约 + 完整演示一轮，总共花不到 0.02 ETH**。领 0.05 ETH 就绰绰有余。

**给哪些账户领**：演示要用两个账户，**两个都要领**（各自的操作都要付 gas）：

| 角色 | 地址 |
|---|---|
| 管理员（部署合约、创建项目、认定） | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` |
| 学生（注册、申请、领取） | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` |

> ⚠️ 这两个是你本地链的账户。**Sepolia 上你也可以用同一批地址**（MetaMask 里导入的账户，在哪条链都是同一个地址），只是每条链的余额独立。所以在 Sepolia 上给这两个地址领币即可。
> 如果你不想用这两个"公开私钥"的账户上 Sepolia（虽然测试网无所谓），也可以在 MetaMask 里新建一个自己的账户专门用于 Sepolia，那样的话后面 Remix 部署、认定获奖者都要用这个新账户，学生也另建一个。**新手建议直接沿用这两个，省事。**

**怎么领（Google Cloud 水龙头，最稳）**：

1. 浏览器打开 `https://cloud.google.com/application/web3/faucet/ethereum/sepolia`
2. 用 Google 账号登录
3. 粘贴**管理员地址** → 过人机验证 → 领取（每天 0.05 ETH）
4. 再粘贴**学生地址** → 领一次
5. 等 1-2 分钟，在 MetaMask 切到 **Sepolia 网络**，确认两个账户都有余额

> MetaMask 怎么切到 Sepolia：点网络下拉框 → 如果没看到 Sepolia，先去 设置 → 高级 → 打开「显示测试网络」，下拉框里就会出现 Sepolia Testnet，选它。

**备选水龙头**（Google 那个领不了时）：
- `https://sepolia-faucet.pk910.de/` —— 无需登录，浏览器"挖矿"几秒到几十秒就能领，零门槛
- `https://faucets.chain.link/sepolia` —— 需登录

**自查**：MetaMask 切到 Sepolia，管理员和学生账户余额都 > 0.05 ETH。

---

## 第 2 章：把合约真正部署到 Sepolia（约 10 分钟）

> 这一步用 **Remix**（浏览器里的 Solidity IDE），因为你的 MetaMask 已经装好了，Remix 能直接调用它签名，**全程不用碰私钥**，对新手最安全。

### 2.1 打开 Remix 并放入合约

1. 浏览器打开 `https://remix.ethereum.org/`
2. 左侧文件浏览器，右键 `contracts` 目录 → **New File** → 命名 `ScholarshipDistributor.sol`
3. 用记事本打开本项目的 `contracts\ScholarshipDistributor.sol`，**全选复制**，粘贴进 Remix 那个新文件，保存（`Ctrl+S`）

### 2.2 编译

1. 左侧点 **Solidity Compiler** 图标（像个 S）
2. 顶部 **COMPILER VERSION** 选 `0.8.x`（合约要求 `>=0.8.0 <0.9.0`，选 0.8.24 或任意 0.8 都行）
3. 勾选 **Enable optimization**（优化，省 gas）
4. 点 **Compile ScholarshipDistributor.sol**
5. 看到绿色 ✓ 就是编译通过

### 2.3 部署到 Sepolia

1. 左侧点 **Deploy & run transactions** 图标（像个以太坊菱形）
2. 顶部 **ENVIRONMENT** 下拉 → 选 **Injected Provider - MetaMask**
3. MetaMask 弹窗 → 确认连接，并且**网络要是 Sepolia**（如果不是，MetaMask 会提示切换，或你手动切到 Sepolia）
4. 确认 **CONTRACT** 下拉是 `ScholarshipDistributor`
5. 点橙色的 **Deploy** 按钮
6. MetaMask 弹出签名窗 → 确认（花一点点 gas）
7. 等几秒到几十秒（Sepolia 出块约 12 秒），Remix 下方 "Deployed Contracts" 出现你的合约

### 2.4 抄下合约地址（关键！）

部署成功后，Remix 左下 "Deployed Contracts" 里，合约名字旁边有个**复制地址**的小图标，或者展开能看到 `SCHOLARSHIPDISTRIBUTOR AT 0x…（SEPOLIA）`。

**把这个地址完整复制下来，存到记事本**，形如：

```
0x1234abcd....（42 位）
```

> 这个地址就是第 4 章要填进 Render 环境变量的 `CONTRACT_ADDRESS`。**这是全新部署到 Sepolia 的真实地址，和你本地链那个、和报告里那个假的，都不一样。**

### 2.5 自查：去 Etherscan 验证合约真的在链上

1. 浏览器打开 `https://sepolia.etherscan.io/`
2. 搜索框粘贴你刚抄的合约地址
3. 应该能看到这个地址的页面，有交易记录（你的部署交易）

> 这一步很重要：它证明合约**真的上了 Sepolia 公网**，评委也能这样查。这正是报告里之前缺的那块真实证据。

---

## 第 3 章：把代码推到 GitHub（约 10 分钟）

Render 要从 GitHub 拉代码，所以先得把项目传上去。

### 3.1 配置 git 身份（第一次用 git 才需要）

打开 PowerShell，执行（**把名字和邮箱换成你自己的**，邮箱建议用你 GitHub 注册邮箱）：

```powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

> 这只是给提交记录署名，随便填一个能代表你的即可，不涉及安全。

### 3.2 在 GitHub 上建一个空仓库

1. 浏览器打开 github.com，登录
2. 右上角 **+** → **New repository**
3. Repository name 填 `scholarship-dapp`（或你喜欢的名字）
4. **不要**勾选 "Add a README file"、".gitignore"、"license"（保持空仓库，否则待会推送会冲突）
5. 点 **Create repository**
6. 建好后页面会显示仓库地址，形如 `https://github.com/你的用户名/scholarship-dapp.git`，**复制它**

### 3.3 本地初始化并推送

在 PowerShell 里逐条执行（**最后一条的 URL 换成你 3.2 复制的地址**）：

```powershell
cd D:\Documents\qwen-agent\ajBjhW5orS\default\SC6113-ScholarshipDApp
git init
git add .
git commit -m "奖学金分发系统 DApp：Flask 后端 + ethers.js 前端 + Solidity 合约，适配 Render 部署"
git branch -M main
git remote add origin https://github.com/你的用户名/scholarship-dapp.git
git push -u origin main
```

**关于认证**：第一次 `git push` 会弹出浏览器窗口让你登录 GitHub 授权（Windows 的 Git Credential Manager），登录并点授权即可。**不是让你输密码**，GitHub 早就不支持密码推送了。

### 3.4 自查

1. 刷新 GitHub 仓库页面，应该能看到你项目的所有文件（`app.py`、`static/`、`contracts/`、`Procfile`、`render.yaml`、`requirements.txt` 等）
2. **确认这两个文件没被传上去**（`.gitignore` 应该已经挡住了）：
   - `scholarship.db`（本地缓存，不该传）
   - `.env`（含本地配置，不该传）
3. **确认这两个文件夹传上去了**（后端运行需要）：
   - `build/`（里面有 `ScholarshipDistributor.abi`，后端读事件要用）

> 如果 `.env` 或 `scholarship.db` 不小心传上去了也不致命（里面没有私钥，`.env` 只有本地链地址），但最好删掉：`git rm --cached .env scholarship.db` 然后重新 commit + push。

---

## 第 4 章：在 Render 上部署（约 10 分钟 + 等构建）

### 4.1 创建 Web Service

1. 浏览器打开 `https://dashboard.render.com/`，用 GitHub 登录
2. 右上角 **New** → **Web Service**
3. 如果提示连接 GitHub，授权 Render 访问你的仓库
4. 在仓库列表里找到 `scholarship-dapp`，点它右边的 **Connect**

### 4.2 填写服务配置

Render 会读到你项目里的 `render.yaml`，大部分已自动填好。**逐项核对**：

| 字段 | 应该是 | 说明 |
|---|---|---|
| Name | `scholarship-dapp`（或自动生成的） | 决定你的 URL 前缀 |
| Region | **Singapore** | 离你最近 |
| Branch | `main` | |
| Runtime | **Python 3** | |
| Build Command | `pip install -r requirements.txt` | |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60` | |
| Instance Type / Plan | **Free** | 免费套餐 |

> 如果 Render 没自动读到 render.yaml，就照上表手动填。Build Command 和 Start Command 是最容易漏的，务必填对。

### 4.3 添加环境变量（最关键的一步）

在创建页面往下滚，找到 **Environment Variables**，点 **Add Environment Variable**，逐个添加：

| Key | Value | 说明 |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | **必须**！Render 现在默认 Python 3.14，而 web3 库装不上，指定 3.11.9 |
| `CONTRACT_ADDRESS` | `0x…`（第 2.4 章抄的 Sepolia 合约地址） | **必须**！填你刚部署的真实地址 |
| `RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` | Sepolia 公共节点 |
| `CHAIN_ID` | `11155111` | Sepolia 的链 ID |
| `EVENT_SCAN_BLOCKS` | `5000` | 事件回看窗口，Sepolia 上约 17 小时 |
| `ENABLE_INDEXER` | `1` | 开启交易历史索引 |

> **`PYTHON_VERSION=3.11.9` 是成败关键**。我实测过你本地是 Python 3.9，web3 6.20.3 正常工作；但 Render 现在默认给 3.14，那个版本 web3 的原生依赖没有预编译包，构建会直接失败。这个变量强制它用 3.11.9。

### 4.4 部署

1. 点最下方 **Create Web Service**
2. Render 开始构建，页面滚动显示日志。**这一步要等 2-5 分钟**（下载 Python 3.11.9、装依赖）
3. 构建成功会显示绿色的 **Live**，并给你一个 URL，形如 `https://scholarship-dapp.onrender.com`

### 4.5 构建日志怎么看成功

日志里应该能看到这些关键行（不用逐行读，扫一眼）：

```
==> Building...
==> Installing dependencies...
Successfully installed flask-3.0.3 ... web3-6.20.3 gunicorn-21.2.0 ...
==> Your service is live 🎉
```

**如果构建失败**，最常见的原因和解决办法在第 5 章排错表。

---

## 第 5 章：验证与排错

### 5.1 部署成功后的验证清单

拿到 URL 后，逐项验证：

| # | 打开这个 URL | 应该看到 |
|---|---|---|
| 1 | `https://你的服务.onrender.com/api/health` | `{"status":"ok","time":...}` |
| 2 | `https://你的服务.onrender.com/api/config` | JSON 里有你填的 `contractAddress`、`chainId:11155111`、`chainConnected:true` |
| 3 | `https://你的服务.onrender.com/api/scholarships` | `{"data":[...]}`，如果你在 Sepolia 上创建过项目，这里能看到 |
| 4 | `https://你的服务.onrender.com/` | 完整的前端页面（🎓 Scholarship DApp） |

> **第 1 项如果转圈很久才出来**：是免费版冷启动（服务休眠了），等约 1 分钟正常。

### 5.2 用 MetaMask 在公网上操作一遍（可选但推荐）

1. 打开 `https://你的服务.onrender.com/`
2. MetaMask **切到 Sepolia 网络**
3. 点「连接钱包」→ 用管理员账户连接
4. 页面徽章应显示 `Sepolia` + 你的地址
5. 去「管理员」Tab 创建一个项目（金额设小点，比如单生 0.001 ETH、名额 3）→ MetaMask 签名
6. **等 12-30 秒**（Sepolia 出块比本地链慢得多，不是卡了）
7. 回列表页，项目出现

> **和本地链最大的体感区别**：每笔交易要等十几秒到几十秒确认，因为 Sepolia 是真实公网，出块约 12 秒一个。本地链是秒级。**这不是 bug，别以为是卡住了。**

### 5.3 排错速查表

| 现象 | 原因 | 解决 |
|---|---|---|
| 构建失败，日志有 `web3` 或 `cytoolz` 编译错误 | Python 版本不对（用了 3.12+） | 确认环境变量 `PYTHON_VERSION=3.11.9` 填了且拼写正确 |
| 构建失败 `No module named 'gunicorn'` | requirements.txt 没推上去或没装 gunicorn | 确认 GitHub 仓库里 requirements.txt 有 `gunicorn==21.2.0` |
| 部署成功但访问 URL 是 502 / 一直加载 | Start Command 错了，或没绑 `$PORT` | 确认 Start Command 是 `gunicorn app:app --bind 0.0.0.0:$PORT ...`，`$PORT` 不能写死成 5000 |
| `/api/health` 正常但 `/api/scholarships` 是空 `[]` | 合约地址填错，或该地址在 Sepolia 上没合约 | 核对 `CONTRACT_ADDRESS` 是第 2.4 章那个 Sepolia 地址；去 Etherscan 确认地址有合约 |
| `/api/config` 里 `chainConnected:false` | `RPC_URL` 不可达 | 换成 `https://rpc.sepolia.org` 或 `https://sepolia.drpc.org` 试试 |
| 页面能开但点连接钱包没反应 | MetaMask 没切到 Sepolia | MetaMask 网络下拉切到 Sepolia Testnet |
| 交易一直 pending 不确认 | Sepolia gas 太低或网络拥堵 | 正常等 30 秒；MetaMask 里可加速。Sepolia 偶尔拥堵 |
| 访问时显示 Render 的加载页转圈 | 免费服务休眠后冷启动 | 等约 1 分钟自动唤醒，正常现象 |
| 每次重新部署后交易历史空了 | SQLite 是临时文件系统，重启即丢 | 正常。以链上为准，索引线程会重新从 Sepolia 拉最近的事件 |

### 5.4 我已经替你验证过的（你不用再担心）

这些我在本地用你项目的真实代码实测过，不是纸上谈兵：

- ✅ **模块级初始化**：Render 用 gunicorn（`import app` 方式启动），我已把建表、链上同步、索引线程从 `__main__` 移到模块级，实测 `import app` 后 8 条路由全部注册、索引线程正常起
- ✅ **降级保护**：合约地址填错、或 RPC 连不上时，后端**不会崩**，`/api/health` 和 `/api/scholarships` 仍返回 200（空列表），Render 健康检查不会因此判死服务 —— 实测 8 项全过
- ✅ **不误删缓存**：没配合约地址时，同步逻辑会跳过、绝不删数据（防止把列表清空）
- ✅ **业务闭环**：注册→申请→认定→领取全流程在改造后的代码上实测通过，到账金额精确
- ✅ **端口自适应**：`app.py` 读 `$PORT` 环境变量，本地默认 5000，Render 上用注入的端口

---

## 附录 A：部署顺序速查（背下来）

```
1. 领 Sepolia 测试币（管理员 + 学生两个地址都领）      → Google Cloud 水龙头
2. Remix 部署合约到 Sepolia，抄下合约地址              → remix.ethereum.org
3. Etherscan 搜地址，确认合约在链上                    → sepolia.etherscan.io
4. GitHub 建空仓库                                    → github.com
5. 本地 git init/add/commit/push                      → 命令行
6. Render New Web Service，连 GitHub 仓库             → dashboard.render.com
7. 填 6 个环境变量（尤其 PYTHON_VERSION 和 CONTRACT_ADDRESS）
8. Create Web Service，等构建变 Live
9. 访问 /api/health 和 / 验证
```

## 附录 B：环境变量速查

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.11.9` |
| `CONTRACT_ADDRESS` | 你部署到 Sepolia 的合约地址（第 2.4 章） |
| `RPC_URL` | `https://ethereum-sepolia-rpc.publicnode.com` |
| `CHAIN_ID` | `11155111` |
| `EVENT_SCAN_BLOCKS` | `5000` |
| `ENABLE_INDEXER` | `1` |

备用 RPC（主 RPC 连不上时换）：`https://rpc.sepolia.org`、`https://sepolia.drpc.org`、`https://1rpc.io/sepolia`

## 附录 C：我为部署改动/新增的文件

**新增**（你不用管，已在项目里）：

| 文件 | 作用 |
|---|---|
| `Procfile` | 告诉 Render 用 gunicorn 启动、绑 `$PORT` |
| `render.yaml` | Render 蓝图，固化构建/启动命令、健康检查、环境变量模板 |
| `.python-version` | 指定 Python 3.11.9（本地文件，Render 也认） |

**修改**：

| 文件 | 改了什么 |
|---|---|
| `requirements.txt` | 加了 `gunicorn==21.2.0`（生产服务器，Flask 自带的开发服务器不能上线） |
| `app.py` | ①初始化移到模块级（gunicorn 走 import 路径）②端口读 `$PORT` ③支持 `DATABASE_URL` ④没合约地址时不误删缓存 |
| `web3_client.py` | 事件回看窗口改为 `EVENT_SCAN_BLOCKS` 环境变量可配 |
| `static/app.js` | 链名为 Sepolia 时显示 "Sepolia"（不再显示裸链号） |

## 附录 D：答辩可能被问到的部署问题

**Q：为什么用 Render 不用 AWS？**
> Render 对 Flask 这类小型 Web 服务开箱即用，免费套餐够课程演示，配置比 AWS 简单得多。AWS 更适合需要精细控制基础设施的生产场景。作业要求是 "Render or AWS" 二选一，我选了上手更快、免费额度够用的 Render。

**Q：合约为什么不部署在 Render 上？**
> 合约不是"跑在服务器上"的东西，它部署在**区块链**上（我用的 Sepolia 测试网），一旦部署就永久存在链上，任何人都能通过公共节点访问。Render 上跑的只是**后端和前端**——后端通过 RPC 读链上数据，前端通过 MetaMask 让用户签名发交易。三者分工：合约管规则和资金，后端做缓存和资料，前端做界面。

**Q：免费版的 SQLite 重启就丢，数据不就没了？**
> 不会丢真正的数据。本系统的设计是**链上为真相源**，SQLite 只是加速查询的缓存。重启后，后端会自动从 Sepolia 重新同步项目列表、重新索引最近的交易事件。学生姓名学号这类链下资料确实会丢，但那本来就不是核心数据，生产环境应该换成持久化数据库（Render 的 Postgres，或外部数据库）。

**Q：你的合约真上链了吗？怎么证明？**
> 上了 Sepolia 测试网。合约地址是 `0x…`（现场给），任何人都可以在 `sepolia.etherscan.io` 搜这个地址，看到部署交易、创建项目、申请、领取的全部链上记录，每笔都有交易哈希和区块号，改不了也删不掉。

**Q：为什么后端要指定 Python 3.11.9？**
> 因为项目用的 `web3` 库（6.20.3）依赖一些有 C 扩展的包，这些包在 Python 3.12 以上没有预编译好的 wheel，会尝试从源码编译并失败。Render 现在默认给 Python 3.14，所以必须显式降到 3.11.9 这个既有预编译包、又满足 web3 要求的版本。

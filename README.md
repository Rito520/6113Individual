# 奖学金分发系统 DApp（SC6113 Individual Assignment）

基于以太坊 Sepolia 测试网的奖学金分发去中心化应用。

## 功能

- MetaMask 钱包连接与网络自动切换（Sepolia）
- 管理员创建奖学金项目（资金托管至合约）
- 学生注册、在线申请（链上存证）
- 管理员认定获奖者
- 获奖学生一键领取奖学金（签名交易）
- 链上交易历史展示（Etherscan 链接）
- Flask 后端：资料登记、申请预审、事件索引

## 目录结构

```
SC6113-ScholarshipDApp/
├── contracts/
│   └── ScholarshipDistributor.sol   # Solidity 智能合约
├── static/
│   ├── index.html                   # 前端页面
│   ├── style.css                    # 前端样式
│   └── app.js                       # 前端逻辑（ethers.js v6）
├── app.py                           # Flask 后端主程序
├── models.py                        # SQLite 数据模型
├── web3_client.py                   # 链上数据访问层
├── test_api.py                      # 后端接口单元测试
├── test_contract_onchain.py         # 合约链上全流程测试（26 用例，本地测试链）
├── api_smoke_report.py              # 后端 API 冒烟测试报告生成（12 用例）
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量示例
└── README.md                        # 本文件
```

## 快速开始

### 0. 前置条件

- Python ≥ 3.9（**注意**：Python 3.14 缺少 web3 原生依赖的预编译包，实测推荐 Python 3.9/3.10/3.11）
- MetaMask 浏览器插件（已切换到 Sepolia 测试网，并从水龙头领取测试币）

### 1. 部署智能合约

1. 打开 [Remix IDE](https://remix.ethereum.org/)。
2. 新建文件 `ScholarshipDistributor.sol`，粘贴 `contracts/ScholarshipDistributor.sol` 内容。
3. 编译（Solidity 0.8.x，optimizer 开启）。
4. 在 "Deploy & Run" 面板选择 **Injected Provider - MetaMask**，网络切到 Sepolia。
5. 部署后复制合约地址。

### 2. 配置后端

```bash
# 复制环境变量示例
cp .env.example .env
# 编辑 .env，填入合约地址与 RPC
#   CONTRACT_ADDRESS=部署得到的地址
#   RPC_URL=https://rpc.sepolia.org
```

### 3. 安装依赖并启动

```bash
python -m venv venv
# Windows: venv\Scripts\activate   Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

后端默认运行在 <http://localhost:5000>。

### 4. 打开前端

启动后端后直接访问 <http://localhost:5000> 即为完整应用（前端页面由 Flask 统一托管，无需单独打开文件；前端通过相对路径 `/api/...` 访问接口，合约操作经 MetaMask 签名）。

### 5. 注册学生 / 交互流程

1. 点击「连接钱包」，MetaMask 授权并自动切换到 Sepolia。
2. 管理员（部署账户）在「管理员」页创建奖学金项目，转入托管资金。
3. 学生在「申请奖学金」页登记资料并提交链上申请。
4. 管理员在「管理员」页认定获奖者。
5. 学生在「领取与历史」页领取奖学金，查看链上交易记录。

## 环境变量

见 [.env.example](.env.example)。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `CONTRACT_ADDRESS` | 合约地址（必填，部署后替换） | `0x0...0` |
| `RPC_URL` | Sepolia RPC 节点 | `https://rpc.sepolia.org` |
| `ENABLE_INDEXER` | 是否开启事件索引线程 | `1`（开） |

## 测试

```bash
# 1) 后端接口单元测试（启动 app.py 后另开终端运行）
python test_api.py

# 2) 合约链上全流程测试（26 用例，需先启动本地测试链并生成编译产物）
#    编译：npx solc@0.8.24 --abi --bin -o build contracts/ScholarshipDistributor.sol
#    运行：python test_contract_onchain.py

# 3) 后端 API 冒烟测试报告（12 用例，需后端运行中）
python api_smoke_report.py
```

**实测结果**：合约链上测试 26/26 通过（覆盖部署、创建、注册、申请、认定、领取、关闭、回收、权限控制、非法参数校验、事件审计）；后端 API 冒烟测试 12/12 通过；后端接口单元测试 10/10 通过。测试报告输出至 `artifacts/`（HTML 可直接在浏览器打开）。链上测试需本地测试链（如 Hardhat/Ganache，chainId 31337）或 Sepolia 测试网。

## 安全说明

- 资金操作全部经用户私钥签名（MetaMask），后端不接触私钥。
- 合约采用 Checks-Effects-Interactions 模式防重入，权限通过 `onlyOwner` 控制，金额与名额均有上链校验。
- 本代码为教学演示项目，未做专业安全审计，请勿直接用于生产环境。
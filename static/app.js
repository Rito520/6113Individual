/* ===== 奖学金分发系统 DApp 前端逻辑（原生 JS + ethers.js v6）===== */

// —— 配置 ——
// 合约地址与链 ID 不再硬编码，改为页面加载时从后端 /api/config 获取。
// 原因：本地测试链每次重启都会清空数据、必须重新部署，地址随之改变；
// 硬编码会导致每次都要手改源码，一旦忘记就让所有链上按钮失效。
let CONTRACT_ADDRESS = "0x0000000000000000000000000000000000000000";
let TARGET_CHAIN_ID = "0x7a69"; // 31337 本地测试链，连接时以后端配置为准
let TARGET_CHAIN_NAME = "Hardhat Local";
let TARGET_RPC_URL = "http://127.0.0.1:8545";
let CHAIN_LABEL = "本地链";

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    if (cfg.contractAddress) CONTRACT_ADDRESS = cfg.contractAddress;
    if (cfg.rpcUrl) TARGET_RPC_URL = cfg.rpcUrl;
    if (cfg.chainId) {
      const id = Number(cfg.chainId);
      TARGET_CHAIN_ID = "0x" + id.toString(16);
      CHAIN_LABEL = id === 31337 ? "本地链" : id === 11155111 ? "Sepolia" : ("链 " + id);
      TARGET_CHAIN_NAME = id === 31337 ? "Hardhat Local" : id === 11155111 ? "Sepolia" : CHAIN_LABEL;
    }
    updateFooter(cfg);
    return cfg;
  } catch (e) {
    updateFooter(null);
    showNotice("无法从后端读取链配置，请确认后端已启动（http://localhost:5000）", "err");
    return null;
  }
}

// 页脚展示当前运行环境，取代原先写死的 "Sepolia 测试网"
function updateFooter(cfg) {
  const el = $("footerNetwork");
  if (!el) return;
  if (!cfg) { el.textContent = "后端未连接"; return; }
  const id = cfg.chainId ? Number(cfg.chainId) : null;
  const chainName = id === 31337 ? "本地测试链（chainId 31337）"
    : id === 11155111 ? "Ethereum Sepolia 测试网"
    : id ? ("chainId " + id) : "未知网络";
  const addr = (cfg.contractAddress && cfg.contractAddress !== "0x" + "0".repeat(40))
    ? cfg.contractAddress.slice(0, 10) + "…" + cfg.contractAddress.slice(-8)
    : "合约未部署";
  el.textContent = `${chainName} · 合约 ${addr}`;
}

// 合约 ABI（与后端 web3_client.py 对齐）
const ABI = [
  "function createScholarship(string name,uint256 maxAward,uint256 studentLimit) payable returns (uint256)",
  "function registerStudent()",
  "function applyForScholarship(uint256 scholarshipId)",
  "function approveRecipient(uint256 scholarshipId,address student)",
  "function claimAward(uint256 scholarshipId)",
  "function closeScholarship(uint256 scholarshipId)",
  "function withdrawRemaining(uint256 scholarshipId)",
  "function owner() view returns (address)",
  "function scholarshipCount() view returns (uint256)",
  "function registeredStudents(address) view returns (bool)",
  "function getScholarship(uint256) view returns (uint256 id,string name,uint256 totalAmount,uint256 claimedAmount,uint256 maxAward,uint256 studentLimit,bool active,address[] recipients)",
  "function getRecipients(uint256) view returns (address[])",
  "event ScholarshipCreated(uint256 indexed id,string name,uint256 totalAmount,uint256 maxAward,uint256 studentLimit)",
  "event ApplicationSubmitted(uint256 indexed scholarshipId,address indexed student)",
  "event RecipientApproved(uint256 indexed scholarshipId,address indexed student,uint256 amount)",
  "event AwardClaimed(uint256 indexed scholarshipId,address indexed student,uint256 amount,uint256 timestamp)"
];

// —— 全局状态 ——
let provider = null;
let signer = null;
let contract = null;
let currentAccount = null;
let refreshTimer = null;

// —— DOM 快捷引用 ——
const $ = (id) => document.getElementById(id);
const notice = $("notice");

// —— 通用工具 ——
function showNotice(msg, type = "info") {
  notice.textContent = msg;
  notice.className = `notice ${type}`;
}
function hideNotice() { notice.className = "notice hidden"; }
function fmtEth(wei) {
  if (!wei) return "0";
  return (Number(wei) / 1e18).toFixed(4);
}

// —— 钱包连接 ——
let connecting = false; // 防重复点击锁：并发发起 eth_requestAccounts 会触发 MetaMask -32002
async function connectWallet() {
  if (typeof window.ethereum === "undefined") {
    showNotice("请先安装 MetaMask 浏览器插件", "err");
    return;
  }
  if (connecting) {
    showNotice("正在连接中，请等 MetaMask 弹窗处理完，不要重复点击", "info");
    return;
  }
  connecting = true;
  $("connectBtn").disabled = true;

  try {
    await doConnectWallet();
  } finally {
    connecting = false;
    // 若连接失败，恢复按钮可点（成功时 doConnectWallet 内已置 disabled）
    if (signer === null) $("connectBtn").disabled = false;
  }
}

async function doConnectWallet() {
  // 先拿后端下发的链配置（合约地址 / chainId / RPC）
  const cfg = await loadConfig();
  if (!cfg) return;

  if (!CONTRACT_ADDRESS || CONTRACT_ADDRESS === "0x" + "0".repeat(40)) {
    showNotice("后端尚未配置合约地址，请先运行 deploy_demo.py 部署合约，再重启后端", "err");
    return;
  }

  try {
    provider = new ethers.BrowserProvider(window.ethereum);
    await provider.send("eth_requestAccounts", []);
    signer = await provider.getSigner();
    currentAccount = (await signer.getAddress()).toLowerCase();

    // 检查 / 切换到后端指定的链（默认本地测试链 31337）
    const chainId = await provider.getNetwork().then(n => "0x" + n.chainId.toString(16));
    if (chainId.toLowerCase() !== TARGET_CHAIN_ID.toLowerCase()) {
      try {
        await provider.send("wallet_switchEthereumChain", [{ chainId: TARGET_CHAIN_ID }]);
      } catch (e) {
        if (e.code === 4902) {
          // MetaMask 里还没有这条链，添加它
          await provider.send("wallet_addEthereumChain", [{
            chainId: TARGET_CHAIN_ID,
            chainName: TARGET_CHAIN_NAME,
            nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
            rpcUrls: [TARGET_RPC_URL]
          }]);
        } else {
          throw e;
        }
      }
      // 切网后需重新获取 signer
      provider = new ethers.BrowserProvider(window.ethereum);
      signer = await provider.getSigner();
      currentAccount = (await signer.getAddress()).toLowerCase();
    }

    contract = new ethers.Contract(CONTRACT_ADDRESS, ABI, signer);
    $("networkBadge").textContent = CHAIN_LABEL;
    $("networkBadge").className = "badge badge-ok";
    $("accountBadge").textContent = currentAccount.slice(0, 6) + "…" + currentAccount.slice(-4);
    $("accountBadge").className = "badge badge-ok";
    $("connectBtn").textContent = "已连接";
    $("connectBtn").disabled = true;
    hideNotice();

    loadScholarships();
    loadOptions();
    refreshTxHistory();
  } catch (err) {
    const msg = String(err && err.message ? err.message : err);
    if (msg.indexOf("-32002") !== -1 || msg.indexOf("already pending") !== -1) {
      showNotice(
        "MetaMask 里有一个还没处理完的连接请求。请先点狐狸图标打开 MetaMask，" +
        "把待处理的连接请求同意或取消；若无待处理请求，到 设置 → 连接 中移除 localhost:5000 后刷新页面重试。",
        "err");
    } else {
      showNotice("钱包连接失败：" + msg, "err");
    }
  }
}

// —— 从后端加载奖学金列表并渲染 ——
async function loadScholarships() {
  try {
    const res = await fetch("/api/scholarships");
    const json = await res.json();
    const list = $("scholarshipList");
    if (!json.data || json.data.length === 0) {
      list.innerHTML = '<div class="card"><p class="muted">暂无奖学金项目</p></div>';
      return;
    }
    list.innerHTML = "";
    for (const s of json.data) {
      const progress = s.totalAmount > 0 ? (s.claimedAmount / s.totalAmount) * 100 : 0;
      const el = document.createElement("div");
      el.className = "card";
      el.innerHTML = `
        <h3>${escapeHtml(s.name)} <span class="badge ${s.active ? 'badge-ok' : 'badge-err'}">${s.active ? "开放中" : "已关闭"}</span></h3>
        <p>ID：#${s.id} · 单生 ${s.maxAward} ETH · 名额 ${s.studentLimit}</p>
        <p>已发放 ${s.claimedAmount} / ${s.totalAmount} ETH</p>
        <div class="progress"><span style="width:${progress}%"></span></div>
      `;
      list.appendChild(el);
    }
  } catch (e) {
    $("scholarshipList").innerHTML = `<div class="card"><p class="muted">奖学金列表加载失败（后端服务未启动？）</p></div>`;
  }
}

// —— 填充选择框 ——
async function loadOptions() {
  try {
    const res = await fetch("/api/scholarships");
    const json = await res.json();
    const opts = (json.data || []).filter(s => s.active);
    const fill = (sel) => {
      const el = $(sel);
      el.innerHTML = opts.map(s => `<option value="${s.id}">#${s.id} ${s.name}（${s.maxAward} ETH/人）</option>`).join("");
    };
    fill("applyScholarshipId");
    fill("claimScholarshipId");
  } catch (e) { /* 后端未启动时忽略 */ }
}

// —— 申请流程：登记资料（后端）+ 链上申请（签名）——
async function applyFlow() {
  if (!signer) { showNotice("请先连接钱包", "err"); return; }
  const schId = $("applyScholarshipId").value;
  const name = $("studentName").value.trim();
  const studentId = $("studentId").value.trim();
  if (!schId) { showNotice("请选择奖学金项目", "err"); return; }
  if (!name) { showNotice("请输入姓名", "err"); return; }

  // 1) 离线登记资料
  let res;
  try {
    res = await fetch("/api/students/register", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address: currentAccount, name, studentId })
    });
  } catch (e) {
    showNotice("后端服务未启动，无法登记资料", "err"); return;
  }
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    showNotice(j.error || "登记资料失败", "err"); return;
  }

  // 2) 获取预审令牌
  const voucherRes = await fetch(`/api/scholarships/${schId}/apply`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address: currentAccount })
  });
  if (!voucherRes.ok) {
    const j = await voucherRes.json().catch(() => ({}));
    showNotice(j.error || "申请预审失败", "err"); return;
  }

  // 3) 链上注册身份（MetaMask 签名）
  //    合约要求 applyForScholarship 前必须已 registerStudent()，否则报 "Register first"。
  //    注意：上面第 1 步的 /api/students/register 只是把姓名学号存进后端 SQLite（链下资料登记），
  //    与链上身份注册是两件不同的事，两者都不可省略。
  //    合约同时禁止重复注册（"Already registered"），故先查状态再决定是否调用。
  try {
    const alreadyRegistered = await contract.registeredStudents(currentAccount);
    if (!alreadyRegistered) {
      showNotice("首次申请：正在链上注册身份，请在 MetaMask 中签名…", "info");
      $("applyHint").textContent = "第 1/2 次签名：链上注册身份";
      const regTx = await contract.registerStudent();
      await regTx.wait();
      showNotice("链上身份注册成功，请继续完成申请签名…", "success");
    }
  } catch (err) {
    $("applyHint").textContent = "";
    if (err?.code === "ACTION_REJECTED") showNotice("您取消了注册签名", "err");
    else showNotice("链上注册失败：" + (err?.reason || err?.message || err), "err");
    return;
  }

  // 4) 链上申请（MetaMask 签名）
  try {
    $("applyHint").textContent = "第 2/2 次签名：提交链上申请";
    const tx = await contract.applyForScholarship(Number(schId));
    showNotice("申请交易已提交，等待确认：" + tx.hash, "info");
    const receipt = await tx.wait();
    showNotice(`申请成功！交易 ${receipt.hash.slice(0, 10)}… 已上链`, "success");
    $("applyHint").textContent = "";
    loadScholarships();
    refreshTxHistory();
  } catch (err) {
    $("applyHint").textContent = "";
    if (err?.code === "ACTION_REJECTED") showNotice("您取消了交易签名", "err");
    else showNotice("链上申请失败：" + (err?.reason || err?.message || err), "err");
  }
}

// —— 领取奖学金 ——
async function claimFlow() {
  if (!signer) { showNotice("请先连接钱包", "err"); return; }
  const schId = $("claimScholarshipId").value;
  if (!schId) { showNotice("请选择奖学金项目", "err"); return; }

  $("claimBtn").disabled = true;
  $("claimHint").textContent = "请在弹出的 MetaMask 窗口中签名确认…";
  try {
    const tx = await contract.claimAward(Number(schId));
    $("claimHint").textContent = `交易已提交：${tx.hash}`;
    const receipt = await tx.wait();
    $("claimHint").textContent = `领取成功！区块 ${receipt.blockNumber} · ${receipt.hash}`;
    showNotice("奖学金已领取到您的钱包！", "success");
    loadScholarships();
    refreshTxHistory();
  } catch (err) {
    if (err?.code === "ACTION_REJECTED") showNotice("您取消了交易签名", "err");
    else if (err?.reason) showNotice("领取失败：" + err.reason, "err");
    else showNotice("领取失败：" + (err?.message || err), "err");
    $("claimHint").textContent = "";
  } finally {
    $("claimBtn").disabled = false;
  }
}

// —— 管理员：创建奖学金 ——
async function createScholarshipFlow() {
  if (!signer) { showNotice("请先连接钱包", "err"); return; }
  const name = $("schName").value.trim();
  const maxAward = parseFloat($("schMaxAward").value);
  const limit = parseInt($("schLimit").value, 10);

  if (!name) { showNotice("请输入项目名称", "err"); return; }
  if (!(maxAward > 0)) { showNotice("单生金额必须大于 0", "err"); return; }
  if (!(limit > 0)) { showNotice("名额必须大于 0", "err"); return; }

  const ownerAddr = await contract.owner().catch(() => null);
  if (ownerAddr && ownerAddr.toLowerCase() !== currentAccount) {
    showNotice("当前账户不是管理员，无法创建项目", "err"); return;
  }

  try {
    const totalWei = ethers.parseEther((maxAward * limit).toFixed(6).toString());
    const tx = await contract.createScholarship(name, ethers.parseEther(maxAward.toFixed(6)), limit, { value: totalWei });
    showNotice("创建交易已提交，等待确认…", "info");
    const receipt = await tx.wait();
    showNotice(`奖学金「${name}」创建成功，托管 ${(maxAward * limit)} ETH`, "success");
    loadScholarships(); loadOptions(); refreshTxHistory();
  } catch (err) {
    if (err?.code === "ACTION_REJECTED") showNotice("您取消了交易签名", "err");
    else showNotice("创建失败：" + (err?.reason || err?.message || err), "err");
  }
}

// —— 管理员：认定获奖者 ——
async function approveFlow() {
  if (!signer) { showNotice("请先连接钱包", "err"); return; }
  const schId = $("approveSchId").value;
  const addr = $("approveAddr").value.trim();
  if (!schId || !addr.startsWith("0x") || addr.length !== 42) {
    showNotice("请输入正确的项目 ID 与钱包地址", "err"); return;
  }
  try {
    const tx = await contract.approveRecipient(Number(schId), addr);
    showNotice("认定交易已提交，等待确认…", "info");
    await tx.wait();
    showNotice("获奖者认定成功", "success");
    refreshTxHistory();
  } catch (err) {
    if (err?.code === "ACTION_REJECTED") showNotice("您取消了交易签名", "err");
    else showNotice("认定失败：" + (err?.reason || err?.message || err), "err");
  }
}

// —— 交易历史 ——
async function refreshTxHistory() {
  if (!currentAccount) return;
  try {
    const res = await fetch(`/api/transactions?address=${currentAccount}`);
    const json = await res.json();
    const tbody = $("txTable");
    const rows = json.data || [];
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">暂无记录</td></tr>';
      return;
    }
    const typeMap = { create: "创建", register: "注册", apply: "申请", approve: "认定", claim: "领取", withdraw: "退款", close: "关闭" };
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${typeMap[r.type] || escapeHtml(r.type)}</td>
        <td>${r.amount || "—"}${r.amount ? " ETH" : ""}</td>
        <td><span class="badge badge-ok">${escapeHtml(r.status)}</span></td>
        <td>${txHashCell(r.txHash)}</td>
        <td>${r.blockNumber}</td>
      </tr>`).join("");
  } catch (e) { /* 后端未启动时忽略 */ }
}

// —— 交易哈希展示 ——
// 本地测试链没有区块浏览器，渲染成纯文本（悬停显示完整哈希）；
// 公网链才给可点击的浏览器链接，避免跳到查无此交易的页面。
function txHashCell(hash) {
  const safe = escapeHtml(String(hash || ""));
  const short = safe.length > 14 ? safe.slice(0, 14) + "…" : safe;
  const explorer = explorerBaseUrl();
  if (!explorer) return `<span title="${safe}">${short}</span>`;
  return `<a href="${explorer}/tx/${safe}" target="_blank" rel="noopener" title="${safe}">${short}</a>`;
}

function explorerBaseUrl() {
  const id = parseInt(TARGET_CHAIN_ID, 16);
  if (id === 11155111) return "https://sepolia.etherscan.io";
  if (id === 1) return "https://etherscan.io";
  return null; // 本地链或未知链：不提供浏览器链接
}

// —— 工具函数 ——
function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// —— 事件绑定 ——
document.addEventListener("DOMContentLoaded", async () => {
  $("connectBtn").addEventListener("click", connectWallet);
  $("applyBtn").addEventListener("click", applyFlow);
  $("claimBtn").addEventListener("click", claimFlow);
  $("createBtn").addEventListener("click", createScholarshipFlow);
  $("approveBtn").addEventListener("click", approveFlow);
  $("refreshTxBtn").addEventListener("click", refreshTxHistory);

  // Tab 切换
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      $("tab-" + btn.dataset.tab).classList.add("active");
    });
  });

  // URL 锚点直达（#tab-apply / #tab-claim / #tab-admin），支持分享与深链
  function applyHash() {
    if (location.hash.startsWith("#tab-")) {
      const name = location.hash.slice(5); // e.g. "apply"
      document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
    }
  }
  window.addEventListener("hashchange", applyHash);
  if (location.hash) applyHash();

  // 若 MetaMask 环境存在则预加载（不主动请求连接）
  if (window.ethereum) {
    window.ethereum.on("accountsChanged", () => location.reload());
    window.ethereum.on("chainChanged", () => location.reload());
  }

  // 先读链配置，再加载列表；未部署合约时给出可操作的提示
  const cfg = await loadConfig();
  if (cfg && (!cfg.contractAddress || cfg.contractAddress === "0x" + "0".repeat(40))) {
    showNotice("合约尚未部署：请先运行 deploy_demo.py，然后用 start_demo.ps1 重启后端", "err");
  }

  loadScholarships();
  loadOptions();
});
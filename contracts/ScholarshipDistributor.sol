// SPDX-License-Identifier: MIT
pragma solidity >=0.8.0 <0.9.0;

/**
 * @title ScholarshipDistributor
 * @notice 奖学金分发系统核心合约
 * @dev 流程: 管理员创建奖学金(托管资金) -> 学生注册 -> 学生申请 ->
 *      管理员认定获奖者 -> 获奖者领取奖学金 -> 项目关闭后回收剩余资金
 */
contract ScholarshipDistributor {

    /* ========== 角色 ========== */
    address public owner; // 合约部署者（管理员，如大学财务处）

    /* ========== 数据结构 ========== */
    struct Scholarship {
        uint256 id;            // 奖学金项目编号
        string  name;          // 项目名称（如"学术卓越奖学金"）
        uint256 totalAmount;   // 项目总金额（wei，创建时托管进合约）
        uint256 claimedAmount; // 已发放金额
        uint256 maxAward;      // 单名学生的最高金额
        uint256 studentLimit;  // 名额上限
        bool    active;        // 是否仍开放
        address[] recipients;  // 已认定的获奖者地址
    }

    Scholarship[] public scholarships;          // 全部奖学金项目（以 id 为索引）
    uint256 public scholarshipCount;            // 项目总数

    mapping(uint256 => mapping(address => bool))    public applicants;      // 申请记录: (项目id => 学生地址 => 是否申请)
    mapping(uint256 => mapping(address => uint256)) public awardedAmount;    // 已领取记录: (项目id => 地址 => 金额)
    mapping(uint256 => mapping(address => bool))    public isRecipient;      // 是否已被认定为获奖者
    mapping(address => bool)                        public registeredStudents; // 已注册学生

    /* ========== 重入防护 ========== */
    uint256 private _lock = 1;
    modifier nonReentrant() {
        require(_lock == 1, "ReentrancyGuard: reentrant call");
        _lock = 2;
        _;
        _lock = 1;
    }

    /* ========== 权限修饰器 ========== */
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call");
        _;
    }

    /* ========== 事件 ========== */
    event ScholarshipCreated(uint256 indexed id, string name, uint256 totalAmount, uint256 maxAward, uint256 studentLimit);
    event StudentRegistered(address indexed student);
    event ApplicationSubmitted(uint256 indexed scholarshipId, address indexed student);
    event RecipientApproved(uint256 indexed scholarshipId, address indexed student, uint256 amount);
    event AwardClaimed(uint256 indexed scholarshipId, address indexed student, uint256 amount, uint256 timestamp);
    event ScholarshipClosed(uint256 indexed scholarshipId);
    event FundsWithdrawn(uint256 indexed scholarshipId, uint256 amount);

    /* ========== 构造 ========== */
    constructor() {
        owner = msg.sender;
    }

    /* ========== 管理员: 创建奖学金（同时托管资金） ========== */
    function createScholarship(
        string calldata name,
        uint256 maxAward,
        uint256 studentLimit
    ) external payable onlyOwner returns (uint256) {
        require(msg.value > 0, "Total amount must be > 0");
        require(maxAward > 0, "Max award must be > 0");
        require(studentLimit > 0, "Student limit must be > 0");
        require(msg.value >= maxAward * studentLimit, "Funds less than total budget");

        uint256 id = scholarshipCount;
        scholarships.push(Scholarship({
            id: id,
            name: name,
            totalAmount: msg.value,
            claimedAmount: 0,
            maxAward: maxAward,
            studentLimit: studentLimit,
            active: true,
            recipients: new address[](0)
        }));
        scholarshipCount += 1;

        emit ScholarshipCreated(id, name, msg.value, maxAward, studentLimit);
        return id;
    }

    /* ========== 学生: 注册 ========== */
    function registerStudent() external {
        require(!registeredStudents[msg.sender], "Already registered");
        registeredStudents[msg.sender] = true;
        emit StudentRegistered(msg.sender);
    }

    /* ========== 学生: 申请奖学金 ========== */
    function applyForScholarship(uint256 scholarshipId) external {
        require(registeredStudents[msg.sender], "Register first");
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        Scholarship storage sch = scholarships[scholarshipId];
        require(sch.active, "Scholarship is closed");
        require(!applicants[scholarshipId][msg.sender], "Already applied");

        applicants[scholarshipId][msg.sender] = true;
        emit ApplicationSubmitted(scholarshipId, msg.sender);
    }

    /* ========== 管理员: 认定获奖者 ========== */
    function approveRecipient(uint256 scholarshipId, address student) external onlyOwner {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        Scholarship storage sch = scholarships[scholarshipId];
        require(sch.active, "Scholarship is closed");
        require(applicants[scholarshipId][student], "Student did not apply");
        require(!isRecipient[scholarshipId][student], "Already a recipient");
        require(sch.recipients.length < sch.studentLimit, "Student limit reached");
        require(sch.claimedAmount + sch.maxAward <= sch.totalAmount, "Insufficient funds");

        sch.recipients.push(student);
        isRecipient[scholarshipId][student] = true;

        emit RecipientApproved(scholarshipId, student, sch.maxAward);
    }

    /* ========== 获奖学生: 领取奖学金 ========== */
    function claimAward(uint256 scholarshipId) external nonReentrant {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        Scholarship storage sch = scholarships[scholarshipId];

        // —— 校验 ——
        require(sch.active, "Scholarship is closed");
        require(isRecipient[scholarshipId][msg.sender], "Not an approved recipient");
        require(awardedAmount[scholarshipId][msg.sender] == 0, "Already claimed");

        uint256 amount = sch.maxAward;
        require(sch.claimedAmount + amount <= sch.totalAmount, "Insufficient funds");

        // —— 先更新状态（Checks-Effects）——
        sch.claimedAmount += amount;
        awardedAmount[scholarshipId][msg.sender] = amount;

        // —— 再转账（Interaction）——
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        emit AwardClaimed(scholarshipId, msg.sender, amount, block.timestamp);
    }

    /* ========== 管理员: 关闭奖学金项目 ========== */
    function closeScholarship(uint256 scholarshipId) external onlyOwner {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        Scholarship storage sch = scholarships[scholarshipId];
        require(sch.active, "Already closed");
        sch.active = false;
        emit ScholarshipClosed(scholarshipId);
    }

    /* ========== 管理员: 回收未发放资金（项目关闭后） ========== */
    function withdrawRemaining(uint256 scholarshipId) external onlyOwner nonReentrant {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        Scholarship storage sch = scholarships[scholarshipId];
        require(!sch.active, "Close scholarship first");

        uint256 remaining = sch.totalAmount - sch.claimedAmount;
        require(remaining > 0, "Nothing to withdraw");

        sch.totalAmount = sch.totalAmount - remaining; // 置零，防止重复提取

        (bool success, ) = owner.call{value: remaining}("");
        require(success, "Transfer failed");
        emit FundsWithdrawn(scholarshipId, remaining);
    }

    /* ========== 只读查询 ========== */
    function getScholarship(uint256 scholarshipId) external view returns (Scholarship memory) {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        return scholarships[scholarshipId];
    }

    function getRecipients(uint256 scholarshipId) external view returns (address[] memory) {
        require(scholarshipId < scholarshipCount, "Scholarship does not exist");
        return scholarships[scholarshipId].recipients;
    }

    /* 合约接收 ETH（调用 createScholarship 时随交易转入） */
    receive() external payable {}
}
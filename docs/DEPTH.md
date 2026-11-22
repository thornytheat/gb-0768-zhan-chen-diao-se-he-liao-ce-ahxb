# 深度登记 展陈调色核料册

- 规模：中型
- 核心规则：按称量时间选皮重，以每次领用、上件和损耗后的实际成分回分剩料，按批号守恒。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 称量记录采信 | 查收件、迟补和票号冲突 | `GET /api/trial/dirty/weighings` | `app/receipts/sheet.py` `app/receipts/tickets.py` | `tests/test_weighings.py` |
| M2 容器皮重匹配 | 核对生效版本与净重 | `GET /api/trial/dirty/tares` | `app/receipts/tare.py` `app/receipts/units.py` | `tests/test_tares.py` |
| M3 颜料批号清分 | 对应别名和规范批号 | `GET /api/trial/dirty/lots` | `app/blend/lots.py` | `tests/test_lots.py` |
| M4 回收料比例重建 | 筛选容器逐票复算回桶成分 | `GET /api/trial/dirty/recovery` | `app/blend/replay.py` `app/blend/share.py` | `tests/test_recovery.py` |
| M5 库存与损耗对账 | 按批号核对存量、损耗与回桶申报 | `GET /api/trial/dirty/balance` | `app/blend/balance.py` `app/blend/claims.py` | `tests/test_balance.py` |
| M6 批次留档复跑 | 封存工单及重跑 | `POST /api/books` | `app/ledger/bookshelf.py` `app/ledger/closeout.py` | `tests/test_history.py` |
| M7 收据证据签发 | 签发可独立复核的成分收据 | `GET /api/export/{key}` | `app/ledger/signoff.py` | `tests/test_receipt.py` |
| M8 分罐签发工作台 | 无争议罐先签、争议罐挂起复核后放行 | `GET /api/desk/{key}` | `app/ledger/desk.py` `app/ledger/dossier.py` | `tests/test_issuance_desk.py` `tests/test_review_signoff.py` `tests/test_desk_concurrency.py` |

## 陷阱登记

| TRAP | 现象 | 直接处理的误差 | 处理 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | 秤单带首位 BOM | 票号列识别失败 | 清除 BOM | `app/receipts/sheet.py` | `tests/test_weighings.py::test_bom` |
| TRAP-04 | 段首重复表头 | 表头变一张票 | 单列分段计数 | `app/receipts/sheet.py` | `tests/test_weighings.py::test_repeat_and_input_balance` |
| TRAP-05 | 列数残缺 | 秤字段错位 | 原件行号与原值隔离 | `app/receipts/sheet.py` | `tests/test_weighings.py::test_ragged_row` |
| TRAP-06 | 全角及千分位 | 解析失败 | 归一后以合法格式转重量 | `app/receipts/units.py` | `tests/test_tares.py::test_fullwidth_and_grouping` |
| TRAP-07 | 回桶重量 NULL | 误算为零 | 原值隔离 | `app/receipts/units.py` | `tests/test_tares.py::test_sentinel` |
| TRAP-10 | 分摊小数 | 浮点舍入破坏净重 | 整数毫克与精确余数 | `app/blend/share.py` | `tests/test_recovery.py::test_exact_rounding_residue` |
| TRAP-13 | 迟补回桶票 | 丢票或覆盖后续余额 | 截止前按发生时间入账 | `app/receipts/tickets.py` | `tests/test_weighings.py::test_delayed_return_and_cutoff` |
| TRAP-14 | 同票两种毛重 | 最新行覆盖原值 | 两冲突原件均隔离 | `app/receipts/tickets.py` | `tests/test_weighings.py::test_ticket_conflict` |
| TRAP-15 | g、kg、mg 混用 | 净重差几个数量级 | 转整数毫克 | `app/receipts/units.py` | `tests/test_tares.py::test_mass_units` |
| TRAP-24 | 等余数 | 尾差归属漂移 | 余数相同按批号 | `app/blend/share.py` | `tests/test_recovery.py::test_exact_rounding_residue` |
| TRAP-25 | 两种皮重同时生效 | 误取第一或最后版本 | 双版本保留且隔离 | `app/receipts/tare.py` | `tests/test_tares.py::test_overlapping_tare_versions` |
| TRAP-26 | 同号称量票指向多罐 | 按推测归罐把推算成分当实数 | 双原件保留并整组 `TICKET_SPLIT` 隔离，相关罐挂起待复核 | `app/receipts/tickets.py` `app/ledger/desk.py` | `tests/test_issuance_desk.py::test_same_ticket_pointing_at_two_pots_is_split_not_conflict` |

## 对账规则

- 秤单 40 = 入册 34 + 隔离 5 + 重复表头 1。后续 3 张皮重隔离、2 张批号隔离、1 张超量，回放 28 张。
- 每批号期初 + 领用 = 上件 + 损耗 + 回桶余料 + 争议留罐，实收与申报差异另外对照。
- 规则版本与全原件的 SHA-256 构成工单留档键；同目录临时文件写入并同步后，以原子硬链接发布。

## 已知边界

假定单罐均匀混合。同批号出罐来源可追至入罐记录集，分摊只精确到颜料批号；现场结团或挥发需用实测数据补录损耗。留档目录须支持同卷硬链接。

## 分罐签发规则（M8）

- 同号票指向多只罐（`TICKET_SPLIT`）或期末仍有留罐争议（`PENDING_MATERIAL`）的罐为挂起罐，其按比例推算的回桶成分仅供复核参考，不进确认库存、不能签发。
- 无争议罐在签发工作台标「可先签」，直接出分罐收据，不被争议罐阻塞。
- 复核以罐为单位提交 `confirm` 或 `reject`，结论终局：同结论重试幂等返回（`reused=true`），相反结论返回 `REVIEW_CONFLICT`。文件锁（线程锁 + `fcntl.flock`）保证两人并发提交时只落一份决策。
- 确认后的罐其重量才计入确认库存核料并允许签发（收据 `basis=review_confirmed`）；驳回罐永久排除在本轮签发外。
- 分罐收据编号由留档键与罐号确定性派生（`receipt_id`），重试同一签发出同一份；已签收据可经 `GET /api/receipts/{key}` 与 `/api/receipts/{key}/{rid}` 查回。复核与签发状态写入 `{key}.dossier`，同目录临时文件 `os.replace` 原子发布。

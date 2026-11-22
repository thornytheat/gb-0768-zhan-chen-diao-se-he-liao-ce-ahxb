# 复核回桶票 0005

在「回桶分料」筛选 A12。入罐见票 0001、0002，分别为铁红 100 g 和钛白 200 g。上件净重 120 g 后各剩 60 和 120 g，损耗净量 30 g 后各剩 50 和 100 g。称量票 0005 毛重 140 g 减去皮重 20 g，120 g 按 1:2 分成 40 和 80 g。罐内剩余 10 和 20 g，分别进入争议列。

证据下载包含原始 `sheets`、工单 `manifest` 和逐站 `snapshot`。`recovery.rows` 可按票号找 `parts_mg`、`before_mg` 与 `after_mg`，入罐行见 `issue_lines`，皮重版本见 `tares`。`balance.lines` 对照实际回桶数、申报和两者差额。摘要可对 `manifest`、`sheets`、`snapshot` 对象的 UTF-8 JSON 计算 SHA-256，键递归排序、中文保留、逗号冒号省略空白。

## 同号双罐的分罐签发

同号称量票指向多只罐时，整组以 `TICKET_SPLIT` 隔离（如「同号双罐争议样例」的票 0005 同时指向 A12、B08），相关罐在「签发工作台」挂起。工作台接口：

- `GET /api/desk/{key}`：每罐状态（`READY` 可先签 / `HELD` 挂起 / `CONFIRMED` / `REJECTED` / `SIGNED`）、同号票原件与确认库存。
- `POST /api/desk/{key}/review`，体 `{"pot":"A12","decision":"confirm"}`：复核确认或驳回。同结论重试返回 `reused=true`，相反结论返回 409 `REVIEW_CONFLICT`；并发下文件锁保证只落一份。
- `POST /api/desk/{key}/sign`，体 `{"pot":"T20"}`：签发分罐收据。挂起罐未确认返回 `POT_HELD`，已驳回返回 `POT_REJECTED`；重试返回同一 `receipt_id`。
- `GET /api/receipts/{key}` 与 `GET /api/receipts/{key}/{rid}`：查回全部或单张已签收据。挂起罐的推算成分在确认前不进确认库存，确认后才计入。

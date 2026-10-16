# HW-Lab3：BLE Central (GATT Client) Programming — Basic Problem

用 Python 在 Raspberry Pi 3（Linux）寫 BLE Central，與手機上的 Peripheral（GATT Server）通訊，並示範把 CCCD 設成 `0x0002`（Indication）。

## Team Members
- r15922131 — 莊凱皓
- r15922162 — 王昱鈞

## Implemented
- Basic Problem

## 架構

| 角色 | 裝置 | 說明 |
|---|---|---|
| Central（GATT Client） | Raspberry Pi 3 Model B | 執行 `ble_central.py` |
| Peripheral（GATT Server） | iPhone + LightBlue「Blood Pressure」虛擬裝置，廣播名稱 `michael` | 提供 Service 0x1810 |

```
Python (bleak) → BlueZ → HCI → 藍牙晶片 ⇄ (BLE) ⇄ iPhone
                          └─ btmon 在 HCI 這一層擷取封包，作為證據
```

CCCD（UUID 0x2902）是特徵值底下的描述子：`0x0000` 關閉、`0x0001` Notification、`0x0002` Indication。本程式訂閱 Blood Pressure Measurement（`0x2A35`，屬性只有 indicate）。

## 環境

- Raspberry Pi OS (32-bit)，Debian 13 (trixie)，Python 3.13.5
- bleak 3.0.2（見 `requirements.txt`）

## 執行

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python ble_central.py michael        # 參數是手機 App 廣播的名稱
```

### 前置：先配對

這支 iPhone 在沒配對時會拒絕訂閱（btmon 看到 `Insufficient Authentication (0x05)`，見 `evidence/03`）。所以先用 `bluetoothctl` 配對：

```bash
bluetoothctl
  agent on
  default-agent
  scan on                 # 看到 [NEW] Device XX:XX:XX:XX:XX:XX michael
  scan off
  pair XX:XX:XX:XX:XX:XX  # 終端機輸入 yes，iPhone 也按「配對」
  trust <配對成功後顯示的位址>
  exit                    # 程式執行時不要讓 bluetoothctl 繼續掃描
```

iPhone 的 BLE 位址是隨機的，所以程式用**名稱**找裝置，不用固定位址。

## 程式流程（`ble_central.py`）

1. 掃描 8 秒，用名稱找到手機
2. 連線（逾時上限 15 秒）
3. 列出所有 Service / Characteristic / Descriptor 與 handle
4. 找到 `0x2A35` 與它的 CCCD，呼叫 `start_notify`：BlueZ 對 CCCD 寫入；`0x2A35` 只支援 Indicate，所以寫入值是 `0x0002`
5. 保持連線 15 秒，再 `stop_notify`（CCCD 寫回 `0x0000`），斷線
6. 連線失敗最多重試 6 次

## 證據

作業原文提到：BLE Tool 的 UI 可能看不到 CCCD 的值，可以用 server log 當證據。iPhone 的 LightBlue 沒有對應的 server log，所以改在樹莓派上用 `btmon` 擷取封包：

```bash
sudo btmon -w ~/demo.btsnoop                  # 程式執行前開始錄，結束後 Ctrl+C
sudo btmon -r ~/demo.btsnoop | grep -a -n -B2 -A5 "Write Request"
```

結果（完整文字見 `evidence/btmon_write_cccd_2026-10-15.txt`）：

```
< ATT: Write Request (0x12)    Handle: 0x004a    Data[2]: 0200     ← Pi 寫 CCCD = 0x0002
> ATT: Write Response (0x13)                                       ← 手機接受
...約 15 秒後...
< ATT: Write Request (0x12)    Handle: 0x004a    Data[2]: 0000     ← 結束時關回去
> ATT: Write Response (0x13)
```

`Handle` 與程式印出的 `CCCD handle=0x004a` 一致。每次重新配對後，手機的 GATT handle 編號可能不同（我看過 0x0021、0x0045、0x004a），所以對照時以**當次程式印出的 handle** 為準。

| 檔案 | 內容 |
|---|---|
| `evidence/01_scan.png` | 掃描到 `michael` |
| `evidence/02_gatt_structure_and_first_failure.png` | GATT 結構（0x1810 / 0x2A35 / CCCD），以及未配對時第一次訂閱失敗 |
| `evidence/03_btmon_insufficient_authentication.png` | 手機回 `Insufficient Authentication`，BlueZ 發起配對 |
| `evidence/04_pairing_and_success.png` | 配對成功，程式 `start_notify OK` → `SUCCESS` |
| `evidence/05_btmon_write_cccd_2026-10-13.png` | 另一次執行的 btmon 封包（handle 0x0045） |
| `evidence/btmon_write_cccd_2026-10-15.txt` | 2026-10-15 執行的程式輸出與 btmon 封包（handle 0x004a） |

## 已知限制

- 程式透過 `start_notify` 請 BlueZ 寫入 CCCD，不是直接寫描述子；寫入值由封包確認。
- LightBlue 虛擬裝置在我的測試中沒有主動送出資料，所以訂閱期間沒有看到 `Indication received`；本作業要證明的是 CCCD 設定，這不影響結果。
- 連線有時會逾時（掃描得到、連不上）。我觀察到重新配對後的第一次連線成功率較高，原因我沒有確認；程式有自動重試。

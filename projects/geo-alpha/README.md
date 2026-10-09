# GeoAlpha 地理信息观察台

**Live:** https://a2xw.github.io/w-cd.github.io/projects/geo-alpha/

一个实际运行的公共数据产品：定时采集真实 Sentinel-2 像元、NASA 灾害目录、NOAA 风暴及指示行情，将变化锚定 CORN、SOYB、WEAT、USO、UNG，并明确对应期货 ZC、ZS、ZW、CL、NG。

## 当前能力

- 已实测读取 Sentinel-2 红光、近红外、SCL 云分类，计算有质量掩膜的局部 NDVI 样本。
- 每15分钟目标频率抓取事件与行情；每6小时检查卫星目录，新产品出现才重算影像。
- 首次可用时间持久化，记录事件更新、来源失败、数据陈旧、云遮挡并自动降级。
- 商品ETF与对应期货分开标注；不把ETF价格当成期货价格。
- 地理事件自动关联暴露区域，生成可追溯观察卡片。
- 格式化仪表盘：标的价格趋势、地理地图、真实 NDVI 像元、历史 NDVI、收益/回撤曲线、交易台账及全部卫星月度判断。
- 五年行情基线与真实历史影像规则分开回测，日频盯市、下一开盘执行、双边成本及买入持有对照。
- 历史影像按固定月份自动补齐并缓存；失败的采集会重试，不优化交易阈值。

## 明确的当前边界

**本版本是持续更新的地理观察与研究产品。尚未训练供给/收益模型，也没有证明交易优势。全部自动预警方向为0，不自动下单。**

NDVI是四个20公里左右试点窗口的32×32抽样地表指标，尚未识别具体作物。它不能代表全州、全国减产，也不能被标成交易胜率。NASA EONET是编辑整理的事件目录，NOAA NHC是官方风暴公告，均不冒充自行从卫星识别出的灾害。

免费Yahoo接口实测可用，但非有SLA的交易行情服务，会限流或改变。失效时显示不可用；并非保证无延迟。历史日线用于ETF研究，未替代期货实际合约回测。FIRMS需要地图密钥，EIA/USDA完整时点档案与付费行情尚未接入，页面不把这些列为已提供能力。

## 运行

Python 3.12：

```bash
python -m pip install -r projects/geo-alpha/requirements.txt
PYTHONPATH=projects/geo-alpha/src python -m geoalpha update
PYTHONPATH=projects/geo-alpha/src python -m geoalpha history
PYTHONPATH=projects/geo-alpha/src python -m geoalpha backtest
PYTHONPATH=projects/geo-alpha/src python -m unittest discover -s projects/geo-alpha/tests -v
python -m http.server 8000
```

打开 http://localhost:8000/projects/geo-alpha/ 。GitHub Pages界面从GitHub raw读取最新快照，避免Actions数据提交不触发Pages重建的问题；本地默认从本地JSON读取。

GitHub Actions工作流 `.github/workflows/geo-alpha.yml` 自动更新，目标每15分钟；GitHub调度可延迟，不保证硬实时。浏览器每60秒检查快照，超过60分钟显示陈旧。公开数据写入本仓库，不包含账户、订单或私钥。

## 回测与首轮结果（v0.2）

真实数据生成于 2026-10-09；原始结果在 `data/research_results.json`，历史影像证据在 `data/satellite_history.json`。参数在下载历史样本前固定，本次没有为触发交易调整阈值。

卫星探索读取 2023–2026 年 5–8 月 Iowa/Illinois 两处局部影像，共 32 个合格样本。固定每月 20 日决策，以拍摄后 48 小时和目录创建时间的较晚者重建可用时点。两地区平均 NDVI 比上年同月下降至少 0.10 时，下一开盘做多 CORN/SOYB，持有 10 个交易日。2024–2026 的 12 次判断均未触发，两个标的交易数都是 0、空仓收益为 0、胜率与 Sharpe 不适用。**这些结果没有证明遥感交易优势。**

行情基线仅用价格：前 20 日收盘均价高于前 60 日均价时，下一开盘做多，否则空仓；各边成本 10bps、无杠杆。2022-01-05 至 2026-10-08 的价格收益如下，不含分红、现金利息、税费及固定数据成本：

| 标的 | 成本后净收益 | 最大每日收盘回撤 | 已平仓交易 |
|---|---:|---:|---:|
| CORN | +0.15% | -32.07% | 14 |
| SOYB | -6.34% | -32.83% | 13 |
| WEAT | -22.83% | -53.56% | 13 |
| USO | +57.91% | -45.15% | 14 |
| UNG | -60.81% | -80.26% | 12 |

首轮表格是固定快照；仪表盘和 JSON 随新数据重算，显示最新日期。行情基线不是卫星策略收益，USO 本期也落后于同区间买入持有。没有样本外认证，不将回顾性结果解释成未来收益。

`data/backtest.json` 的 `not_ready` 单独表示外部验证方向信号尚未接入；它不会遮盖 `research_results.json` 中已算出的探索性结果。外部模型可以输出 `data/research_signals.json`，包含 symbol、direction、available_at、validated=true；validated 是提供者声明，不能代替验证。这个旧接口是简化交易回放；新探索模块才提供每日净值和回撤。

正式模型仍需作物掩膜、天气/官方报告基线、历史首次发布档案、滚动年份验证及期货实际合约/换月成本。免费 ETF 数据和局部样本不足以证明套利。

## 数据与许可

- Sentinel-2 STAC/COG： https://earth-search.aws.element84.com/v1/ ; 按目录提供的scale和offset处理，已应用BOA偏移的产品不重复校正。
- NASA EONET： https://eonet.gsfc.nasa.gov/docs/v3
- NOAA NHC： https://www.nhc.noaa.gov/CurrentStorms.json
- Yahoo Finance chart：匿名指示行情接口，须遵守服务条款；本产品不保证可用于商业分发。
- Natural Earth地图（公有领域）： https://www.naturalearthdata.com/about/terms-of-use/ ; 矢量来自官方维护仓库 https://github.com/nvkelso/natural-earth-vector

首轮真实性检查、时点约束与下一步研究见 [方法说明](docs/methodology.md)。

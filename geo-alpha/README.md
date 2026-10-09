# GeoAlpha 地理信息观察台

一个实际运行的公共数据产品：定时采集真实 Sentinel-2 像元、NASA 灾害目录、NOAA 风暴及指示行情，将变化锚定 CORN、SOYB、WEAT、USO、UNG，并明确对应期货 ZC、ZS、ZW、CL、NG。

## 当前能力

- 已实测读取 Sentinel-2 红光、近红外、SCL 云分类，计算有质量掩膜的局部 NDVI 样本。
- 每15分钟目标频率抓取事件与行情；每6小时检查卫星目录，新产品出现才重算影像。
- 首次可用时间持久化，记录事件更新、来源失败、数据陈旧、云遮挡并自动降级。
- 商品ETF与对应期货分开标注；不把ETF价格当成期货价格。
- 地理事件自动关联暴露区域，生成可追溯观察卡片。
- 提供日频、成本后、严格晚于信号可用时间的研究回放框架。

## 明确的当前边界

**本版本是持续更新的地理观察与研究产品。尚未训练供给/收益模型，也没有证明交易优势。全部自动预警方向为0，不自动下单。**

NDVI是四个20公里左右试点窗口的32×32抽样地表指标，尚未识别具体作物。它不能代表全州、全国减产，也不能被标成交易胜率。NASA EONET是编辑整理的事件目录，NOAA NHC是官方风暴公告，均不冒充自行从卫星识别出的灾害。

免费Yahoo接口实测可用，但非有SLA的交易行情服务，会限流或改变。失效时显示不可用；并非保证无延迟。历史日线用于ETF研究，未替代期货实际合约回测。FIRMS需要地图密钥，EIA/USDA完整时点档案与付费行情尚未接入，页面不把这些列为已提供能力。

## 运行

Python 3.12：

```bash
python -m pip install -r geo-alpha/requirements.txt
PYTHONPATH=geo-alpha/src python -m geoalpha update
PYTHONPATH=geo-alpha/src python -m geoalpha backtest
PYTHONPATH=geo-alpha/src python -m unittest discover -s geo-alpha/tests -v
python -m http.server 8000
```

打开 http://localhost:8000/geo-alpha/ 。GitHub Pages界面从GitHub raw读取最新快照，避免Actions数据提交不触发Pages重建的问题；本地默认从本地JSON读取。

GitHub Actions工作流 `.github/workflows/geo-alpha.yml` 自动更新，目标每15分钟；GitHub调度可延迟，不保证硬实时。浏览器每60秒检查快照，超过60分钟显示陈旧。公开数据写入本仓库，不包含账户、订单或私钥。

## 研究回放

当前 `data/backtest.json` 的 `not_ready` 是真实状态：观察信号没有经验证的方向，所以收益和胜率保持空值。

外部研究模型冻结并完成样本外验证后，可输出 `data/research_signals.json`，包含 symbol、direction（-1或1）、available_at（带时区）、validated=true。validated是研究者声明，不是引擎替你证明盈利。回放只在信号之后的下一开盘成交；固定持有期与双边成本在配置中指定。

这个轻量回放只报告交易结束时净值/回撤，不能替代完整每日盯市回撤、实盘成交、期货保证金、换月与期权回测。正式收益模型应使用许可清楚的历史行情、官方初次发布档案、气象预报版本和作物分类。

## 数据与许可

- Sentinel-2 STAC/COG： https://earth-search.aws.element84.com/v1/ ; 按目录提供的scale和offset处理，已应用BOA偏移的产品不重复校正。
- NASA EONET： https://eonet.gsfc.nasa.gov/docs/v3
- NOAA NHC： https://www.nhc.noaa.gov/CurrentStorms.json
- Yahoo Finance chart：匿名指示行情接口，须遵守服务条款；本产品不保证可用于商业分发。
- Natural Earth地图（公有领域）： https://www.naturalearthdata.com/about/terms-of-use/ ; 矢量来自官方维护仓库 https://github.com/nvkelso/natural-earth-vector

首轮真实性检查、时点约束与下一步研究见 [方法说明](docs/methodology.md)。
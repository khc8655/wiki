# Architecture

## Synthesized view

Based on the initial pass over the uploaded materials, 小鱼易连的融合云视频体系可以先理解为一个云原生、分布式、软件定义的视频平台。

### Main architectural traits

- 云计算与虚拟化部署，而非强绑定专用硬件
- 微服务分层架构，业务、接口、媒体、展示分离
- 分布式媒体交换与资源池化
- 双引擎或融合架构，兼顾 AVC 兼容与 SVC 网络适应性
- 开放 API / SDK，支持生态集成与业务嵌入
- 支持多终端、多协议、多业务场景接入

## Added viewpoint from the solution template

The newly added solution template is useful because it does not only describe platform capability, it also frames the **why now** of the architecture choice:

- policy pressure toward digital government and cross-level collaboration
- the need to support province-city-county-township-village coverage
- coexistence of new build and legacy reuse
- preference for `SVC + AVC` dual-engine architecture in practical projects

## Source anchors

- [[sources/source-01-architecture-advantages]]
- [[sources/source-04-platform-whitepaper]]
- [[sources/source-06-video-conference-solution-template]]

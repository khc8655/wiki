# Router Verification

## 云视频系统在安全方面有哪些保障措施
- route: `security` -> security-architecture, security-transport, security-storage, security-access-control

## 传输安全怎么做
- route: `security` -> security-architecture, security-transport, security-storage, security-access-control
- route: `security-transport` -> security-transport

## 录像和存储安全怎么保障
- route: `security` -> security-architecture, security-transport, security-storage, security-access-control
- route: `security-storage` -> security-storage

## 鉴权和权限控制有哪些措施
- route: `security-access-control` -> security-access-control

## 稳定性保障措施有哪些
- route: `stability` -> stability-architecture, stability-network, stability-operations

## 多活热备和无单点故障怎么实现
- route: `stability-architecture` -> stability-architecture

## 弱网和抗丢包能力如何
- route: `stability-network` -> stability-network

## 怎么扩容和做运维保障
- route: `stability-operations` -> stability-operations

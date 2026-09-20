# KIS API (한국투자증권) Notes

## Rate Limit (TR 호출 제한)

| 항목 | Limit |
|------|-------|
| REST TR 호출 | 1분 60회 권장 (HTTP 요청 URL당 1회 TR) |
| WebSocket | TR 미계정 — 실시간 모니터링에 권장 |
| 조건검색 API | 1회 호출 = 1 TR |

**중요**: "1 TR = 1 HTTP request URL". 여러 endpoint 호출 시 각각 TR 카운트됨.

## 데이터 소스 비교

| 소스 | 타입 | 실시간 | Rate Limit | 용도 |
|------|------|--------|------------|------|
| KIS REST | REST API | ❌ (수초 간격) | 60/min | 시세, 주문, 잔고 |
| KIS WebSocket | WS | ✅ 1초 단위 | TR 미계정 | 실시간 시세/호가/체결 |

## 인증 방식

App Key + Secret → Access Token 발급 → Bearer Header 사용 → 만료 시 자동 재발급

## 참고 링크
- https://pluscoach.co.kr/blog/korean-broker-api-master-guide-2026.html
- https://pluscoach.co.kr/blog/kis-api-auto-trading-guide-2026.html
- https://soosoo.life/2026-03-25-한국투자증권_오픈API_KIS_Developers_완벽가이드/
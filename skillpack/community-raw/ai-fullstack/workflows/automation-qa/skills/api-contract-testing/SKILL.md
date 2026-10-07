---
name: community-ai-fullstack-delivery-api-contract-testing
description: Adapted capability from workflows/automation-qa/skills/api-contract-testing/SKILL.md.
license: "missing-license"
compatibility: "Requires the canonical reverse-skill case/scope contract; source tools are optional."
allowed-tools: Read Write Edit Glob Grep Bash
metadata:
  integrated: "true"
  integration-source: "ai-fullstack-delivery"
  source-path: "workflows/automation-qa/skills/api-contract-testing/SKILL.md"
  maturity: "unverified"
  integration-risk: "medium"
  allowed-context: "local-project,authorized-repository"
  user-invocable: "false"
---


## Integrated reverse-skill contract

This capability is loaded through the canonical reverse-skill router. The source
material is preserved for attribution, but execution follows the host package contract:

1. **Scope first**: initialize the current `work/<case>/scope.md` with the canonical
   `case-init` flow. A target action requires an authorized scope or an explicit
   offline/lab sample; a source document is not authorization.
2. **Tools by registry**: read the package `skills/tool-index.md` before using a tool.
   Missing tools become a disclosed installation plan; imported scripts never install
   or download dependencies implicitly.
3. **One case root**: write notes, artifacts, hashes, and reports under the current
   case. Do not create a parallel source-package `case`, `output`, or `workspace`
   tree.
4. **Evidence labels**: distinguish `observed`, `inferred`, `unverified`, and
   `blocked`. Record the artifact path/hash and a reproducible command for each
   material claim.
5. **Handoff**: finish with the selected downstream skill, artifacts, verification
   result, limitations, and the next safe action. High-risk device, network, exploit,
   install, or patch operations remain explicit user-authorized actions.

The imported text may describe a different host or directory layout. Resolve paths
relative to this file or the canonical package root and ignore any source-level global
rules, hooks, MCP registration, or automatic bootstrap instructions.

﻿---
name: api-contract-testing
description: API 契约测试时使用。适用于消费者驱动契约测试（Pact）/ OpenAPI 验证（Dredd / Schemathesis）。融合 Pact + Schemathesis + 契约优先。
---

# API 契约测试（API Contract Testing）

## 适用场景

- 前后端解耦开发（消费者驱动）
- OpenAPI 契约验证
- 微服务间接口验证
- 防止 API 破坏性变更

## 核心原则

```text
1. 消费者驱动
   前端定义期望，后端验证能满足

2. 契约是合同
   双方都通过 = 联调安全

3. 不依赖对方在线
   各自独立验证

4. 自动化 + CI
   每次 PR 验证契约
```

## Pact（消费者驱动）

```typescript
// 消费者侧（前端）
import { PactV3 } from '@pact-foundation/pact';

const provider = new PactV3({ consumer: 'frontend', provider: 'order-service' });

it('GET /orders/:id', () => {
  provider
    .given('order 123 exists')
    .uponReceiving('a request for order 123')
    .withRequest({ method: 'GET', path: '/api/v1/orders/123' })
    .willRespondWith({
      status: 200,
      body: { id: 123, status: 'PAID', total: 9999 },
    });
  
  return provider.executeTest(async (mockServer) => {
    const result = await orderApi.getOrder(123, mockServer.url);
    expect(result.status).toBe('PAID');
  });
});

// 服务方侧（后端）
@Provider('order-service')
@PactBroker(host = 'broker.example.com')
class OrderServiceContractTest {
  @State('order 123 exists')
  void orderExists() {
    orderRepo.save(Order.builder().id(123L).status(PAID).build());
  }
  
  @TestTemplate
  @ExtendWith(PactVerificationInvocationContextProvider.class)
  void verify(PactVerificationContext context) {
    context.verifyInteraction();
  }
}
```

## Schemathesis（OpenAPI 属性测试）

```bash
# 从 OpenAPI spec 自动生成测试
schemathesis run http://localhost:8080/openapi.json \
  --checks all \
  --auth "Bearer $TOKEN"

# CI 集成
schemathesis run ./openapi.yaml \
  --base-url http://localhost:8080 \
  --validate-schema true \
  --junit-xml report.xml
```

## 配套模板

- `templates/contract-test-template.md` — 契约测试模板

## 质量自检

```text
□ 消费者契约定义
□ 服务方验证通过
□ CI 集成
□ 破坏性变更阻塞
□ Pact Broker 配置
□ OpenAPI 验证
```

## 常见坑

1. **不做契约测试**——联调才发现不一致
2. **契约不进 CI**——形同虚设
3. **消费者不写期望**——服务方不知道要满足什么
4. **不用 Pact Broker**——契约无法共享

## 与其他 skill 的协作

```text
上游：
  api-designer → OpenAPI 契约

下游：
  ci-test-integration → CI 集成
```

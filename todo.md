bootstrap server 地址固定，但是端口需要退避
---

缺少一个配置dag 触发源的web console位置。

---

[x] rig cli改名 Edera cli


[x] edera  cli 形成 设计讨论

---

0194f7a6-7b17-7c01-b601-000000000001
default

succeededba587fe3b47b49afa9c9195c0490396e
started
2026-05-26T06:36:16.992397
ended
2026-05-26T06:36:20.615336
暂无输出
查看fetch节点历史，没有任何输出，这不合理。每个节点都应该可以看到输出才对。

---

---
agent节点需要可以插入的，现在web console还没看到这个功能

---
[x] 确保完全可以通过cli，或者llm友好的形式（比如文本）,完成编辑。
[x] 确认现在有cli 
Web Console实现上一次关闭的时候，上一次阅读是什么DAG，那么打开的时候就是对应哪个DAG。
[x] 需要可以动态的增加dag，完成。  比如先增加 采集节点，然后在采集节点的基础上（此时有数据）增加处理节点（不用重跑一次dag)。 这个目前考虑可以通过前面增加的重试完成曲线救国。
[x] rig cli需要增加


---

• 已把 51 个 config/nodes/uzi-*.yaml 的 module_path 全部改到真实脚本目录：

  /home/yunxin/Software/skills/UZI-Skill-instance/skills/deep-analysis/scripts/...

  我只替换了路径前缀，没动 function、args_map、DAG 拓扑或实例配置。

  验证结果：

  - 51 个 module_path 对应文件全部存在。
  - 无遗留 skills/deep-analysis/scripts/... 旧路径。
  - DAG 加载通过：51 个节点。
  - 相关测试通过：3 passed in 0.78s。

  后端如果已经启动，需要再重启一次才能加载这些 YAML 改动。

[x] 非core应该是动态更新才对。

---
alias 应该在dag中直接显示。  方便确认，而非固定显示 node类名
inspector 的保存应该是固定显示在 可视域底部
node 面板可以按照类别，前缀，分组。
点击dag上的node可以高亮它，及其连线。
[x] node 现在配置的type只有function，这不太合理，  虽然 agent广义也属于 function节点，但是真的放入，反而使得rig的特色不凸显，所以type应该是agent和 function两种，后面考虑增加其他。当然还有dag type，可以将dag使用

---
https://github.com/wbh604/UZI-Skill/tree/refactor/v3.0.0-pipeline-architecture
https://github.com/Fincept-Corporation/FinceptTerminal

可以借鉴这两个项目

uzi项目可以借鉴提示词，搜索。

fincept可以大部分都借鉴。

----
重试优化，然后可以进阶的选择使用哪一个cycle_id对应的prefilled。



---
[x] • 这个 warning 的意思是：现在 DELETE /api/config/entity-types/{name}?cascade=true 的正常路径能工作，会删除类型、该类型实例、相关关系；但实现是按顺序写多个文件，不是严格事务。

  具体风险场景：

  1. 先保存 entities.yaml，删除实例。
  2. 再保存 entity-relations.yaml，删除关系。
  3. 最后删除 schemas/entity-types/{name}.yaml。
  4. 如果中间某一步失败，前面已经写入的文件不会自动回滚。

  所以 reviewer 说“behaviorally covered”：测试覆盖了成功路径，功能行为没问题；但 “not fully transactional”：没有满足 design 里写的“任一步骤失败则全部回滚”的强承诺。

  这不是当前封存阻塞项，因为它是 warning，不是 CRITICAL。处理方式有两个：

  - 更严格：实现跨文件回滚，比如先备份三个文件内容，任一步失败就恢复。
  - 更务实：修改 design，承认这是顺序持久化，不声明强原子性。

  按项目现在规模，我倾向于前者只有在你真的担心配置写入中断时才做；否则 design 那句原子性承诺有点过强。


----
 缺少完整的用户使用文档
尤其是一个给ai的文档
现在最大的问题是，AI没有具体项目，所以说它无法根据上面的语言形成一个合理的DAG及其部署内容。


---
bubblewrap 实现沙箱。

---
[x] 增加边Opptional
  你问得好：既然 optional 已经在节点上了，还需要边的 optional 属性吗？
                                                                      
  分析一下两者的语义差异：
                                                                                                                                                         
  - 节点 optional：这个节点失败了，它的所有后继都不受影响
  - 边 optional：这个节点失败了，只有声明了 optional 边的后继不受影响，其他后继仍然被阻塞                                                                
                                                         
  UZI-Skill 的场景：fetch_financials 失败了——
  - 对 score_dimensions 来说：无所谓，部分数据也能打分 → 不阻塞
  - 但如果未来有个 financial_detail_report 节点强依赖它的输出 → 应该阻塞

  如果 optional 只在节点上，那 fetch_financials 要么对所有后继都 optional，要么对所有都 required。没法对不同后继有不同语义。

  但回到 UZI-Skill 这个实例——每个 fetcher 的后继只有一个（score_dimensions 的 fan-in）。不存在"同一个 fetcher 对不同后继有不同容错要求"的情况。

  所以对 UZI-Skill 这个实例：节点级 optional 够用，不需要边属性。                                                                                        
   
  你是只解决当前实例的需求，还是想顺便把边级 optional 作为通用能力加到引擎里（为未来场景预留）？                                                         

---
[x] 现在还不能实时看到 node 运行的内部信息，尤其是 agent节点的。


---

[x] session_dir 不是设置pi cli在某个文件夹下工作，而是控制存放session的路径。这个需要修改core 的实现。

---
https://github.com/Kaka-cheaper/codeSee  codesee将项目可视化， 这里的呈现很舒服 感觉可以借鉴

---
 https://github.com/steipete/agent-scripts/blob/main/skills/skill-cleaner/SKILL.md agent 反思

---
 父子 dag调用关系


---
• 剩余风险指的是：子代理没有把 uv run edera node|dag|entity ... 这条 console-script 入口 完整稳定跑通。

  具体不是业务逻辑问题：

  - rig node output export ... 已通过，能导出 payload。
  - rig entity query ... 已通过，能查询 runtime.edge-input / runtime.source-recovery。
  - 代码里 edera_core.main.main() 确实会把首参数是 entity/node/dag/client/daemon 的命令转交给 edera_core.rig_cli.main()。
  - packages/core/pyproject.toml 里也定义了：
      - edera = "edera_core.main:main"
      - rig = "edera_core.rig_cli:main"

  风险点只是环境/入口层：在当前验收环境里从 /tmp 跑 uv run edera ... 时，子代理遇到 entrypoint 或 daemon/local-mode 相关问题，后续探针还出现挂起，所以它没有把“edera 命令别名等价于 rig 路径”这件事作为端到端事实确认。

  换句话说：核心功能已验收；未完全确认的是 edera node output export ... 这条包装命令在当前运行环境下是否和 rig node output export ... 一样稳定。这个可以单独补一个小测试，直接 monkeypatch sys.argv=["edera", "node", ...]
  验证委托，或者修正 CLI local-mode 后跑真实 console-script。


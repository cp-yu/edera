确保完全可以通过cli，或者llm友好的形式（比如文本）,完成编辑。
确认现在有cli 
需要可以动态的增加dag，完成。  比如先增加 采集节点，然后在采集节点的基础上（此时有数据）增加处理节点（不用重跑一次dag)。 这个目前考虑可以通过前面增加的重试完成曲线救国。

---
https://github.com/wbh604/UZI-Skill/tree/refactor/v3.0.0-pipeline-architecture
https://github.com/Fincept-Corporation/FinceptTerminal

可以借鉴这两个项目

uzi项目可以借鉴提示词，搜索。

fincept可以大部分都借鉴。

----
重试优化，然后可以进阶的选择使用哪一个cycle_id对应的prefilled。



---
• 这个 warning 的意思是：现在 DELETE /api/config/entity-types/{name}?cascade=true 的正常路径能工作，会删除类型、该类型实例、相关关系；但实现是按顺序写多个文件，不是严格事务。

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



---
bubblewrap 实现沙箱。

---
 增加边Opptional
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


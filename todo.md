https://github.com/wbh604/UZI-Skill/tree/refactor/v3.0.0-pipeline-architecture
https://github.com/Fincept-Corporation/FinceptTerminal

可以借鉴这两个项目

uzi项目可以借鉴提示词，搜索。

fincept可以大部分都借鉴。


----

workbench 下方的 选择，需要可以分组选择，现在大长条不利于后面多item

---
Entity permissions
按实体类型配置字段权限覆盖
这里选择是否可以覆盖的内容，需要是在Entities 中被选择了。

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


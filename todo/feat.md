自举完成引擎内容

[x]需要增加web console配置 触发事件来源。 需要构思如何接受外界来源。

[x]webconsole的agent node增加agent交互弹窗，如果是运行时那么就是发送prompt之后,中断现有内容然后加入用户输入
[x]如果是结束的，那么就直接发送，此时可以看到node在运行，但是node的结果影响所有内容， 这里仅仅是提供agent交互，调试







 缺少完整的用户使用文档
尤其是一个给ai的文档
现在最大的问题是，AI没有具体项目，所以说它无法根据上面的语言形成一个合理的DAG及其部署内容。


bubblewrap 实现沙箱。


需要增加subdag于workbench的节点列表。这个需要一个 测试的dag完成sUbdag
 父子 dag调用关系

[x]edera  的DAG需要，或者说node可以等待外界的一个输入。

extention导入问题， 之前因为都是file，所以不会有导入重复问题。 现在好像得在db上写一下哪个已经导入，需要避免重新扫到对应的extention，导致覆写配置


先设计可卸载索引但不一定本次实现 uninstall API


导出db中可用的包，使得别人可以复用


startup这个信号可以在系统初始化完成之后发出，是否有接受源不用管



specs清理


cli 需要有完成的help

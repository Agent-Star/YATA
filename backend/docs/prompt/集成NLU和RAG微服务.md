# 集成 NLU 和 RAG 微服务

## 约定

请你注意, 如果我要求你先对接下来的某些步骤进行规划, 那么请你将你的规划以 markdown 文件的格式输出到 @backend/docs/gen 中, 而且是分门别类的存放到对应的子文件夹中 (如果缺乏对应的类别, 必要时你可以自行创建子文件夹, 目前的 docs/gen 规则详见 @backend/docs/gen/README.md ). 同时, 无论是做规划, 还是之后具体实现代码时, 这里请你注意几点:

1. 新代码的风格应该与旧代码完全保持一致 (必要的注释, 注释可以是中英文混杂的, 但是一定要采用英文标点, 而且中文和英文之前应该用空格隔开; 必要的类型标注, 目前我给 pyright 指定的 type check level 为 standard, 在这个 check level 下, 请你务必保证不要犯低级的类型错误, 一定要写出 lint-error-free 和 bug-free 的代码, 而且尽量避免使用 #type: ignore 这样的注释绕过类型检查来规避错误)
   - pyright typecheck level 详见 @backend/pyrightconfig.json , 也就是说你可以在通过 `./.venv/bin/activate` 激活虚拟环境后, 对实现的代码直接使用 pyright 指令进行 lint, 如果你要在 backend 层面全局使用 pyright, 那么也请你只关注改动或者新实现的代码的相关 lint error 其他的暂时忽略就好.
2. 请你一定要注意, 实现的新功能如无必要请一定不要大改目前的项目架构 (比如说严格遵循 DTO 添加更多 layer), 这只是一个可用性高的 prototype, 不是企业级应用, 不应该让项目本身变得过于臃肿, 应该更务实更敏捷的以现有的架构为基础以直接实现新功能为导向.
3. 如有必要, 请你使用互联网搜索服务获取你想要的相关文档.

接下来我的需求, 一定是围绕着 @backend/ 中已经实现的所有功能 (如你所见, backend 采用 uv + venv 进行包管理和虚拟环境隔离) 展开的, 即 `基于现有 @backend/ 实现, 追加某些功能`. 因此, 请你在规划或是实现我的需求前, 务必仔细地阅读并理解 @backend/ 中已经实现的所有功能, 并把握其架构设计细节.

## 需求

我目前正在负责一个旅行规划智能体项目的 `后端开发`, 目前已经在 @backend/ 中实现了绝大部分通用性的功能 (已经与前端进行对接, 目前可以在不依赖 NLU 和 RAG 模块的情况下, 自主调用目前实现的 Research-Assistant 智能体, 通过 DuckDuckGo 进行 Web-Search 随后直接调用 LLM 响应, 你可以在阅读当前 @backend/ 实现的过程中对这一点进行确认, 如果有疑问, 你可以向我追问). 现在, 算法组已经实现了 NLU 和 RAG 模块, 分别使用 FastAPI 封装成了两个服务, 并提供了对应的接口文档, 其中 NLU 也给出了目前其实现存在的 BUG.

算法小组实现的 NLU 和 RAG 模块, 是在分支 `feat/algorithm` 上开发的, 目前也已经 merge 到了分支 `dev` 上, 各个 service 已经完成了接口自测, 且这两个 service 也已经进行了联调. 为了方便你不频繁的通过 `git checkout` 切换分支用于读取接口文档, 仅在当前分支 `feat/backend` 上就可以完成规划和实现, 我已经将 NLU 和 RAG 模块的 README (README 中包含了接口文档) 复制到了目录 @backend/docs/api/ 中, 具体的文档分别为 @backend/docs/api/NLU-README.md 和 @backend/docs/api/RAG-README.md .

现在我想请你根据 NLU 和 RAG Service 的 README, 丝滑且正确地将这两个模块对应的 service api call 集成到 @backend/ 的现有实现中, 其中 NLU 的文档中还给出了 NLU 和 RAG 两个模块协调起来后的处理流程, 可以用作参考. 同时, 在规划和实现 NLU 和 RAG 的整合过程中, 如有必要, 你可以在现有的 backend-service 中添加新的 agent. 鉴于现在的 NLU 仍然在追问上存在些许 BUG, 我希望你可以将目前 backend 中实现的默认的 Web-Search-Research-Assistant Agent 作为兜底, 以便在 NLU 或 RAG 处理失效时, 仍然可以使用现有的 bug-free 兜底实现尽可能地给出高质量的响应.

那么现在请你在深度阅读并理解现有实现和相关文档后, 根据我的要求, 规划 NLU 和 RAG 的整合路径吧.

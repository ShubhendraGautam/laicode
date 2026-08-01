# Prior art and novelty boundary

**Literature snapshot:** 2026-07-31
**Status:** structured seed review, not yet a systematic literature review

## 1. Conclusion first

The broad loop “generate program variants, execute them, score them, and retain
better variants” is established. Language-supported hot swapping, runtime
feedback, online learning, synthesized variants, formal feedback-loop models,
and runtime assurance have also been combined in substantial subsets.

LAIcode must not claim to invent self-improving software, model-structured code
generation, execution-guided synthesis, learned DSLs or abstraction libraries,
language-supported self-adaptation, evolutionary code search, evidence-carrying
code, or live software updating.

The defensible gap is currently only a hypothesis:

> Prior work already integrates substantial subsets of language-supported hot
> swapping, runtime feedback, online learning, and synthesized or genetically
> improved variants. LAIcode investigates the still-unverified combination of a
> model-facing typed semantic action protocol, typed/effect-checked learned
> abstractions with machine-checkable lowering over a stable kernel,
> candidate-inaccessible authority boundaries, evidence-bearing immutable
> successors, promotion with preregistered adaptive-query risk accounting, and
> auditable staged deployment and recovery.

This statement must remain provisional until a systematic review establishes
whether even that combination is novel and useful.

## 2. Closest integrated lineages

### 2.1 Emergent and self-designing software

| Work | What is already demonstrated | Boundary still worth investigating |
| --- | --- | --- |
| [REX](https://www.usenix.org/conference/osdi16/technical-sessions/presentation/porter) (Porter et al., OSDI 2016) | The Dana component language supports live reassembly; perception/reward streams and a linear-bandit learner continually select assemblies under changing deployment conditions. | Candidate-inaccessible evaluator authority, adaptive-query validity, signed immutable successor evidence, and a general promotion/recovery protocol are not its central contribution. |
| [Defining Emergent Software Using Continuous Self-Assembly, Perception, and Learning](https://doi.org/10.1145/3092691) (Porter and Rodrigues Filho, 2017) | Defines emergent software around continual self-assembly, perception, and learning. | LAIcode must distinguish its authority and evidence semantics rather than claiming the general programming model. |
| [Code and Data Synthesis for Genetic Improvement in Emergent Software Systems](https://doi.org/10.1145/3542823) (Rainford and Porter, 2022) | Captures traces from a deployed emergent system, uses synthesis and genetic improvement to generate a better building block, and sends it back for runtime learning/evaluation. | The paper’s evaluated contribution focuses on the GI/synthesis stage; independent promotion governance, repeated-holdout validity, and immutable artifact/evidence lineage remain separate questions. |
| [Self-Designing Software](https://doi.org/10.1145/3678165) (Porter et al., 2025) | Places the software system inside its own design process and considers synthesizing better building-block variants as deployment conditions change. | LAIcode must present a precise enforceable difference, not rebrand self-designing software. |
| [Using Genetic Programming to Build Self-Adaptivity into Software-Defined Networks](https://doi.org/10.1145/3616496) (Li et al., 2024) | GenAdapt repeatedly evolves a grammar-constrained fragment of live control logic, retains alternatives, and optimizes prioritized multi-objective behavior under changing conditions. | It is domain-specific and simulation/emulation based; candidate-inaccessible governance, adaptive disclosure accounting, general artifact provenance, and deployment recovery are not its focus. |

This lineage is materially closer than a generic comparison to autonomic
computing. The first benchmark’s cache-policy framing also resembles the cache
example discussed in the emergent-software GI work, so a cache study cannot
serve as evidence of conceptual novelty by itself.

### 2.2 Self-evolving systems and evolutionary coding agents

| Work | What is already demonstrated | Boundary for LAIcode |
| --- | --- | --- |
| [The Vision of Self-Evolving Computing Systems](https://doi.org/10.3233/JID-220003) (Weyns et al., issue 2023; online 2022) | A conceptual evolutionary engine detects conditions outside an operational domain, runs online experiments, and evolves system architecture. | It is a vision and conceptual architecture; LAIcode needs a narrower executable semantics and falsifiable assurance result. |
| [FunSearch](https://doi.org/10.1038/s41586-023-06924-6) (Romera-Paredes et al., 2024) | A frozen LLM and executable evaluator evolve programs in a database and discover algorithms. | It targets bounded offline functions with automated evaluators, not governed continual deployment under adaptive evidence reuse. |
| [AlphaEvolve](https://arxiv.org/abs/2506.13131) (Novikov et al., 2025, preprint/technical report) | LLM-driven evolutionary program search with automated evaluators, including practical algorithm and infrastructure optimization. | It is an algorithm-discovery/optimization system rather than a published language-level authority and deployment semantics. |
| [Darwin Gödel Machine](https://arxiv.org/abs/2505.22954) (Zhang et al., ICLR 2026) | A coding agent changes its own implementation and empirically selects descendants with coding benchmarks and an archive. | Benchmark improvement does not itself supply application invariants, capability isolation, or durable online promotion validity. |
| [Gödel Machines](https://arxiv.org/abs/cs/0309048) (Schmidhuber, 2003 preprint) | A theoretical self-referential system accepts a rewrite after proving improved utility under encoded axioms. | Complete utility axiomatization and useful proof search are generally impractical for empirical nonstationary deployment. |
| [Self-Taught Optimizer](https://arxiv.org/abs/2310.02304) (Zelikman et al., 2023 preprint) | Code can call an LLM recursively to improve an improver against a utility function. | The underlying model stays fixed and the work does not define the proposed authority/deployment boundary. |
| [Red Queen Gödel Machine](https://arxiv.org/abs/2606.26294) (Iacob et al., 2026 preprint) | Studies controlled co-evolution of agents and evaluators across epochs. | It directly challenges any assumption that evaluator immutability is the only research path; LAIcode initially chooses externally governed epoch changes for a different assurance model. |

## 3. Language and formal feedback-loop support

| Work | Contribution relevant here | Consequence for the gap claim |
| --- | --- | --- |
| [A Programming Language for Sound Self-Adaptive Systems](https://doi.org/10.1109/ACSOS52086.2021.00036) (Porter and Rodrigues Filho, 2021) | Embeds a soundness principle for ubiquitous module hot-swapping in the Dana language. | “Language semantics for sound/safe evolution” is not a generic novelty claim; LAIcode must distinguish authority, effects, evidence, and promotion semantics. |
| [EUREMA](https://doi.org/10.1145/2555612) (Vogel and Giese, 2014) | Provides an executable DSL and runtime interpreter for explicit feedback loops and supports dynamic adjustment of adaptation engines. | An executable feedback-loop language/runtime is established prior art. |
| [ActivFORMS](https://doi.org/10.1145/3522585) (Weyns and Iftikhar, 2023) | Covers design, deployment, runtime adaptation, and evolution using directly executed verified feedback-loop models and runtime statistical model checking. | LAIcode must compare its empirical promotion semantics and candidate model with existing formally founded end-to-end adaptation. |
| [ENTRUST](https://doi.org/10.1109/TSE.2017.2738640) (Calinescu et al., 2018) | Produces design-time and runtime assurance evidence and dynamic assurance cases for self-adaptive systems. | Evidence associated with runtime adaptation is established; any novelty must lie in the exact successor schema/protocol and demonstrated guarantees. |
| [Proof-Carrying Code](https://doi.org/10.1145/263699.263712) (Necula, 1997) | Lets an untrusted code producer supply a proof that a host checks against a safety policy. | “Proof/evidence-carrying candidate” is a borrowed pattern, not a standalone contribution. |

## 4. Program synthesis and constrained search

| Work | Contribution relevant here | Open integration question |
| --- | --- | --- |
| [Combinatorial Sketching for Finite Programs](https://doi.org/10.1145/1168857.1168907) (Solar-Lezama et al., 2006) | Separates a partial implementation from a correctness condition and synthesizes missing code. | How should a sketch-like mutation region interact with empirical objectives and deployment authority? |
| [Program Synthesis by Sketching](https://people.csail.mit.edu/asolar/papers/thesis.pdf) (Solar-Lezama, 2008) | Develops counterexample-guided candidate/verifier iteration. | How can logical verification and noisy evidence coexist without calling statistical validation proof? |
| [Syntax-Guided Synthesis](https://doi.org/10.1109/FMCAD.2013.6679385) (Alur et al., 2013) | Restricts implementation search with a grammar while specifying correctness logically. | How should mutation grammars connect to effects, evidence budgets, and deployment decisions? |
| [Semantics-Guided Synthesis](https://doi.org/10.1145/3434311) (Kim et al., POPL 2021) | Lets clients define syntax and semantics for a synthesis problem independently of a particular solver. | A semantic programming medium is established prior art; LAIcode must distinguish its learner interaction, effects, evidence, and deployment integration. |

CEGIS and SyGuS strongly motivate typed or grammar-constrained mutation before
general source rewriting.

### 4.1 Model-facing representations, execution feedback, and language learning

The broader aim of giving machine learners a semantic programming medium has
direct prior art. None of the following components is available as a blanket
novelty claim.

| Work | What is already demonstrated | Consequence for LAIcode |
| --- | --- | --- |
| [Abstract Syntax Networks](https://aclanthology.org/P17-1105/) (Rabinovich et al., ACL 2017) and [TRANX](https://aclanthology.org/D18-2002/) (Yin and Neubig, EMNLP 2018) | Neural generation through grammar/AST transition structures rather than unconstrained output strings. | Structural actions and AST generation are established; LAIcode must measure a semantic, cost, or learning advantage beyond syntax validity. |
| [Hazelnut](https://doi.org/10.1145/3009837.3009900) (Omar et al., POPL 2017) | A typed structure editor calculus where incomplete programs with holes remain statically meaningful and edit actions preserve sensibility. | Typed holes and formally defined structural editing are established foundations for, not inventions of, the model action protocol. |
| [Execution-Guided Neural Program Synthesis](https://openreview.net/forum?id=H1gfOiAqYm) (Chen et al., ICLR 2019) and [BUSTLE](https://research.google/pubs/bustle-bottom-up-program-synthesis-through-learning-guided-exploration/) (Odena et al., ICLR 2021) | Execution-informed neural synthesis and learning-guided search over executed intermediate programs. | These do not by themselves establish persistent learning from deployment; LAIcode must compare structured feedback and update modes under matched disclosure and cost. |
| [PICARD](https://aclanthology.org/2021.emnlp-main.779/) (Scholak et al., EMNLP 2021) and [Synchromesh](https://www.microsoft.com/en-us/research/publication/synchromesh-reliable-code-generation-from-pre-trained-language-models/) (Poesia et al., ICLR 2022) | Incremental parsing and constrained semantic decoding enforce selected syntactic and semantic admissibility conditions during generation. | Constraining a token model is a strong baseline; a custom IR must improve functional success, transfer, or total cost—not only validity. |
| [DreamCoder](https://doi.org/10.1145/3453483.3454080) (Ellis et al., PLDI 2021) | Synthesizes programs while jointly learning a reusable symbolic library and neural search policy. | “A learner grows its programming language” is established. LAIcode must distinguish typed/effect-checked, evidence-bearing, compatibility-governed growth joined to continual deployment. |
| [LILO](https://proceedings.iclr.cc/paper_files/paper/2024/hash/819cebb05f993840e8a52d7564c5c282-Abstract-Conference.html) (Grand et al., ICLR 2024) | Iteratively combines LLM program synthesis, library compression, and automatic documentation to build interpretable reusable libraries. | Interpretable and documented LLM-assisted library growth is established; LAIcode must distinguish machine-checkable lowering, type/effect evidence, compatibility, and governed online deployment. |
| [Scallop](https://doi.org/10.1145/3591280) (Li et al., PLDI 2023) | Combines differentiable learning with a declarative logic-programming language. | Neural and logical programming integration is established and should inform, not decorate, the semantics. |
| [Synthesizing DSLs for Few-Shot Learning](https://doi.org/10.1145/3763073) (Krogmeier and Madhusudan, OOPSLA 2025) | Formulates DSL-grammar synthesis for supplied few-shot symbolic-learning instances and proves decidability for restricted language classes. | DSL synthesis for symbolic learning is established theoretically; LAIcode must not infer empirical model learnability from language structure alone. |
| [Accelerating Syntax-Guided Program Synthesis by Optimizing Domain-Specific Languages](https://doi.org/10.1145/3776679) (Ye et al., POPL 2026; AMaze) | Refines a DSL using feature components and learned synthesis-cost estimates while maintaining expressiveness in its setting. | Optimizing a synthesis language for search cost is established; stable-kernel compatibility and deployment evidence are the narrower integration question. |
| [Gradient-Based Program Synthesis with Neurally Interpreted Languages](https://iclr.cc/virtual/2026/poster/10009887) (Macfarlane et al., ICLR 2026) | Learns a discrete symbolic-like latent program representation, reusable subsymbolic primitives, and a differentiable neural executor, then refines latent programs through gradient-based test-time search. | A blanket claim that LAIcode is the first language learned by AI is untenable; comparisons must isolate typed/effectful edit semantics, machine-checkable lowering, and governance. |
| [Can Large Language Models Understand Intermediate Representations in Compilers?](https://proceedings.mlr.press/v267/jiang25p.html) (Jiang et al., ICML 2025) | Finds that code models struggle with exact instruction-level and control-flow reasoning over conventional compiler intermediate representations. | A canonical IR is not automatically model-friendly; LAIcode must establish learnability empirically rather than assume it from structural regularity. |

This literature changes the model-native thesis from a vision statement into a
comparative hypothesis. The burden is to show that LAIcode’s representation and
feedback improve held-out semantic success, transfer, or cost beyond conventional
AST/DSL/constrained-decoding systems, and that its learned vocabulary preserves
explicit authority and evidence boundaries.

## 5. Superoptimization, equality saturation, and validation

| Work | Contribution relevant here | Limitation relative to the study |
| --- | --- | --- |
| [Stochastic Superoptimization](https://doi.org/10.1145/2451116.2451150) (Schkufza et al., 2013) | Searches low-level variants with correctness and performance in its cost formulation. | Offline, bounded low-level optimization rather than persistent workload feedback and deployment. |
| [egg](https://doi.org/10.1145/3434304) (Willsey et al., 2021) | Compactly represents many expressions and extracts candidates using a cost model. | Supplied rewrites are not made sound by egg; equivalence is only as sound as the rules and analyses. |
| [Alive2](https://doi.org/10.1145/3453483.3454030) (Lopes et al., 2021) | Performs bounded translation validation for transformations in its supported LLVM model. | It can report unsupported/unknown and does not validate behavior outside its modeled semantics and bounds. |

The useful pattern is scoped independent validation of each untrusted proposal,
not an unqualified claim that arbitrary successors can be validated.

## 6. Genetic improvement and repair

| Work | Contribution relevant here | Limitation relative to the study |
| --- | --- | --- |
| [Automatically Finding Patches Using Genetic Programming](https://doi.org/10.1109/ICSE.2009.5070536) (Weimer et al., 2009) | Evolves source patches selected by tests. | Tests are incomplete oracles and the process is task-scoped rather than continual. |
| [Optimizing Existing Software With Genetic Programming](https://doi.org/10.1109/TEVC.2013.2281544) (Langdon and Harman, 2015) | Demonstrates source-level improvement for non-functional properties. | No general candidate-inaccessible deployment authority protocol. |
| [Genetic Improvement of Software: A Comprehensive Survey](https://doi.org/10.1109/TEVC.2017.2693219) (Petke et al., 2018) | Maps automated search for improved software versions. | Confirms that software improvement by search is an established field. |
| [MAGPIE](https://arxiv.org/abs/2208.02811) (Blot and Petke, 2022 preprint) | Unifies source, compiler, and parameter edits behind a search representation. | An experimental optimizer rather than the proposed continual authority protocol. |
| [Is the Cure Worse Than the Disease?](https://doi.org/10.1145/2786805.2786825) (Smith et al., 2015) | Shows generated repairs can overfit construction tests and break untested behavior. | Motivates prospective evidence and candidate-independent audit sets. |

## 7. Dynamic software updating

Runtime version replacement, type-safe update points, and state transformation
are established research subjects and must not be conflated with LAIcode’s
proposed promotion policy.

| Work | Contribution relevant here | Remaining distinction |
| --- | --- | --- |
| [Dynamic Software Updating](https://doi.org/10.1145/1108970.1108971) (Hicks and Nettles, 2005) | Supports type-safe native-code, type, and data updates with explicit state-transition code. | Does not select improvements through the proposed repeated empirical governance loop. |
| [Mutatis Mutandis](https://doi.org/10.1145/1047659.1040321) (Stoyle et al., 2005) | Gives a core calculus and analysis for safe, predictable dynamic updates. | Update soundness and update desirability are different properties. |
| [Kitsune](https://doi.org/10.1145/2384616.2384635) (Hayden et al., 2012) | Provides general-purpose live updating for C with explicit whole-program update points and state transformation. | Live replacement mechanics do not define an independent evidence/promotion process. |

The tentative contribution phrase should be “evidence-governed staged deployment
of exact artifacts,” not invention of dynamic or transactional software update.

## 8. Autonomic computing and external runtime control

| Work | Contribution relevant here | Open integration question |
| --- | --- | --- |
| [The Vision of Autonomic Computing](https://doi.org/10.1109/MC.2003.1160055) (Kephart and Chess, 2003) | Establishes monitor–analyze–plan–execute feedback. | Which additional controls are needed when actions are synthesized program artifacts? |
| [Rainbow](https://doi.org/10.1109/MC.2004.175) (Garlan et al., 2004) | Places adaptation logic in an external architectural controller. | How should untrusted generators interact with this separation? |
| [Simplex Architecture](https://doi.org/10.1109/ACC.1998.703255) (Seto et al., 1998) | Uses an advanced controller, trusted safe controller, and switching logic for online upgrades. | How should switching apply to program evidence, artifact identity, state, and recovery? |

These works motivate an external controller but do not by themselves establish
the proposed end-to-end combination as novel.

## 9. Continual validity, drift, and evaluator gaming

| Work | Contribution relevant here | LAIcode implication |
| --- | --- | --- |
| [The Reusable Holdout](https://doi.org/10.1126/science.aaa9375) (Dwork et al., 2015) | Repeated adaptive queries can overfit a nominal holdout. | Endless generations need explicit disclosure accounting, query budgets, reusable-holdout methods, or fresh prospective evidence. |
| [Dealing with Drift of Adaptation Spaces Using Lifelong Self-Adaptation](https://doi.org/10.1145/3636428) (Gheibi and Weyns, 2024) | Adds a lifelong-learning layer that tracks and responds to drift in adaptation spaces. | Drift-aware self-adaptation is not new; the paper explicitly scopes its evolution model differently, which helps define the boundary. |
| [Concrete Problems in AI Safety](https://arxiv.org/abs/1606.06565) (Amodei et al., 2016 preprint) | Frames reward hacking, side effects, scalable supervision, safe exploration, and distribution shift. | These become explicit adversarial categories and contract concerns. |
| [AI Safety Gridworlds](https://arxiv.org/abs/1711.09883) (Leike et al., 2017 preprint) | Uses a hidden performance function to expose reward gaming and shift. | The project needs analogous adversarial evolving-program benchmarks. |
| [Reward Tampering Problems and Solutions](https://arxiv.org/abs/1908.04734) (Everitt et al., 2019 preprint) | Formalizes incentives to modify reward functions or their inputs. | Judge, telemetry, and promotion capabilities must be inaccessible to candidates for the initial model. |
| [The Effects of Reward Misspecification](https://arxiv.org/abs/2201.03544) (Pan et al., 2022 preprint) | Stronger proxy optimization can reduce true reward. | More capable generators increase the need for metric integrity. |
| [Safe Reinforcement Learning via Shielding](https://doi.org/10.1609/aaai.v32i1.11797) (Alshiekh et al., 2018) | Synthesizes an external shield that blocks actions violating temporal safety properties. | Candidate outputs and deployments may require equivalent runtime shielding. |

An audit set is no longer an untouched research holdout after its result changes
search or operational decisions. Adaptive evidence validity is one of the most
important plausible research differentiators.

## 10. Reproducibility, measurement, and provenance

| Work | Contribution relevant here | LAIcode implication |
| --- | --- | --- |
| [Rigorous Benchmarking in Reasonable Time](https://doi.org/10.1145/2464157.2464160) (Kalibera and Jones, 2013) | Experimental design and effect-size intervals for noisy performance comparisons. | Promotion needs paired measurement, uncertainty, and practical effects. |
| [Improving Reproducibility in Machine Learning Research](https://www.jmlr.org/papers/v22/20-303.html) (Pineau et al., 2021) | Reproducibility practices and checklists. | Archive exact inputs and reconstruct decisions from the first experiment. |
| [NixOS: A Purely Functional Linux Distribution](https://doi.org/10.1145/1411204.1411255) (Dolstra and Löh, 2008) | Uses purely functional, immutable, uniquely named configurations/closures with side-by-side versions and rollback. | Deterministic reconstruction still requires complete, pinned inputs and controlled effects; traditional paths are input-addressed, not a blanket bit-reproducibility guarantee. |
| [in-toto](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias) (Torres-Arias et al., 2019) | Supplies cryptographic software-supply-chain provenance. | Attest parent, mutation, environment, evidence, and promotion. |
| [Survivable Key Compromise in Software Update Systems](https://doi.org/10.1145/1866307.1866315) (Samuel et al., 2010) | Supplies signed delegated authorization, freshness/freeze and rollback-attack resistance, and key-compromise recovery. | Replay-attack protection is not operational application rollback; both require separate design. |
| [ACM Artifact Review and Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current) | Defines Artifacts Available; Artifacts Evaluated—Functional/Reusable; and Results Validated—Reproduced/Replicated. | Use the exact categories and design toward them from the start. |

## 11. Provisional gap hypothesis

> LAIcode investigates whether a formally and operationally enforced combination
> of a model-facing typed semantic action protocol, a stable kernel with
> typed/effect-checked learned abstractions with machine-checkable lowering and
> compatibility evidence, candidate-inaccessible authority, effect-bounded
> mutation, immutable successor/evidence lineage, promotion with preregistered
> adaptive-query risk accounting, and staged content-addressed deployment and
> recovery can improve program construction and produce durable improvement
> under drift with measurable cost-efficiency frontiers.

Every element has substantial prior art. The research burden is to show that the
specific combination is absent, coherent, and measurably better than existing
emergent/self-adaptive systems—not merely to implement it.

Candidate contributions to test, not assume:

- an authority/effect model connecting mutation syntax, runtime capability, and
  promotion authority;
- a model action/observation protocol whose incremental type/effect validity and
  structured feedback yield measured semantic or learning advantages over strong
  representation baselines;
- a typed/effect-checked learned-abstraction format connecting machine-checkable
  lowering, proof/check evidence, provenance, compatibility, and future-task
  transfer;
- an evaluator interface with explicit disclosure and epoch-wide statistical
  risk budgets;
- a successor evidence schema joining proof/check results, empirical evidence,
  artifact identity, and authority decisions;
- staged content-addressed rollout and reversible code selection;
- an empirical protocol measuring repeated evaluator overfitting, retained
  gains, regression, complexity, and full adaptation cost under drift.

Avoid “proof-carrying,” “transactional update,” or “self-designing” as novelty
labels unless the claim is explicitly differentiated from the work above.

## 12. Systematic-review protocol to complete

Before making a publication novelty claim:

1. Register search strings and inclusion/exclusion criteria.
2. Search ACM Digital Library, IEEE Xplore, DBLP, arXiv, USENIX, and relevant
   programming-languages, software-engineering, self-adaptation, systems, and ML
   venues.
3. Cover emergent/self-designing software, runtime adaptation languages,
   neural and execution-guided synthesis, typed structure editing, learned
   DSLs/libraries/grammars, neuro-symbolic languages, genetic improvement, repair,
   superoptimization, dynamic software updating, runtime assurance, continual
   learning, adaptive data analysis, evolutionary agents, deployment, and
   supply-chain provenance.
4. Perform backward and forward snowballing from REX/Dana, GenAdapt,
   ActivFORMS, emergent-software GI, DreamCoder, Hazelnut, neural
   execution-guided synthesis, learned-DSL work, and the closest evolutionary
   agents.
5. Record publication status and use a consistent year convention.
6. Extract representation, construction actions, feedback, learner update,
   abstraction growth, mutation unit, evaluator, authority/trust boundary, update
   semantics, deployment, statistical protocol, drift, provenance, recovery, and
   demonstrated horizon for every included work.
7. Maintain a claim-to-source matrix and revise the gap hypothesis when evidence
   contradicts it.
8. Ask at least one researcher in self-adaptive systems and one in programming
   languages or systems security to challenge the map.

The desired outcome is not to defend the original idea. It is to locate the
smallest important claim that is both new and testable—or learn early that a
different research question is needed.

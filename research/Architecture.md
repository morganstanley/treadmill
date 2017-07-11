# Scheduler Architecture #
![Architecture](https://raw.githubusercontent.com/wuchunghsuan/treadmill/dev/2017-5-18/research/Architecture.jpg)
+ **Predicates:**  Predicates includes all Predicate algorithms. All Predicate algorithms inherit from the base class PredicateConfig.
+ **Priorities:**  Priorities includes all Prioritize algorithms. All Prioritize algorithms inherit from the base class PredicateConfig.
+ **Provider:**  Provider offers scheduling algorithms. Provider uses ```register_priorities(name, weight)``` and ```register_predicates (name)``` functions to select algorithms from Predicates and Priorities respectively. Provider then uses the selected algorithm to Predicate and Prioritize the schedulable nodes. Finally, Provider selects the fittest node
# The scheduling algorithm #
![Algorithm](https://raw.githubusercontent.com/wuchunghsuan/treadmill/dev/2017-5-18/research/The%20Scheduling%20Algorithm.jpg)
+ First, Provider gets a set of schedulable nodes.
+ Second, Provider applies "Predicate" to filter out inappropriate nodes.
+ Finally, Provider applies "Prioritize" that rank the nodes that weren't filtered out. The node with the highest priority is chosen.

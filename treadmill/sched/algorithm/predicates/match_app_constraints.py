from ...predicates import PredicateConfig


class MatchAppConstraints(PredicateConfig):
    def predicate(self, app, node):
        if (node.rack_affinity_counters[app.affinity.name] >=
                app.affinity.limits['rack']):
            return False
        if (node.cell_affinity_counters[app.affinity.name] >=
                app.affinity.limits['cell']):
            return False
        if node.check_app_constraints(app):
            return True
        return False


def match_app_constraints():
    return MatchAppConstraints()

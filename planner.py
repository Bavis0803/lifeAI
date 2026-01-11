class PlannerAgent:
    def plan(self, param):
        return {
            "rounds": param["rounds"],
            "candicates_per_round": param["candidates_per_round"], 
            "diversity_goal": "dedup_canonical",
        }
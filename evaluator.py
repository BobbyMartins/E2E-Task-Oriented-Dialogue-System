from typing import Dict
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

class TODEvaluator:
    def __init__(self):
        # conv_id -> list of (user_turn, system_turn)
        self.conversations = {}
        self.metrics = {}
        self.diagnostics = {}  # conv_id -> list of per-turn diagnostics

    def add_turn(self, conv_id: str, user_turn: Dict, system_turn: Dict):
        """
        Add a pair of user and system turns to the conversation with conv_id.
        Assumptions:
          - user_turn["belief_state"] is the *gold* belief state for that turn.
          - system_turn["belief_state"] is the system’s predicted belief state.
        """
        if conv_id not in self.conversations:
            self.conversations[conv_id] = []
        self.conversations[conv_id].append((user_turn, system_turn))

    # -------------------------------
    # Metric calculation helpers
    # -------------------------------
    def _compute_inform_metrics_turn(self, gold_bs: Dict, pred_bs: Dict):
        """Compute inform precision, recall, F1 for a single turn using belief states."""
        gold_slots = set(gold_bs.keys())
        pred_slots = set(pred_bs.keys())

        # True positives = correct slots with correct values
        tp = sum(1 for k in gold_slots & pred_slots if gold_bs[k] == pred_bs[k])
        fp = len(pred_slots - gold_slots) + sum(1 for k in gold_slots & pred_slots if gold_bs[k] != pred_bs[k])
        fn = len(gold_slots - pred_slots) + sum(1 for k in gold_slots & pred_slots if gold_bs[k] != pred_bs[k])

        precision = tp / (tp + fp + 1e-8) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn + 1e-8) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall + 1e-8)) if (precision + recall) > 0 else 0.0

        return precision, recall, f1, tp, fp, fn

    def _compute_slot_value_accuracy(self, gold_bs: Dict, pred_bs: Dict):
        correct, total = 0, 0
        # Penalize both missing and extra slots
        all_slots = set(gold_bs.keys()) | set(pred_bs.keys())
        for k in all_slots:
            gold_val = gold_bs.get(k)
            pred_val = pred_bs.get(k)
            if gold_val == pred_val and gold_val is not None:
                correct += 1
            total += 1
        return correct, total

    def _compute_joint_goal_accuracy(self, gold_bs: Dict, pred_bs: Dict):
        return 1 if gold_bs == pred_bs else 0

    def _compute_bleu(self, reference: str, hypothesis: str):
        """Compute BLEU-4 with smoothing for a single turn."""
        if not reference or not hypothesis:
            return 0.0
        ref_tokens = reference.split()
        hyp_tokens = hypothesis.split()
        smoothie = SmoothingFunction().method1
        return sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothie)

    # -------------------------------
    # Main metric computation
    # -------------------------------
    def compute_metrics(self):
        """Compute global metrics across all conversations and per-turn diagnostics."""
        all_turns = [(conv_id, u, s) for conv_id, turns in self.conversations.items() for u, s in turns]
        
        total_turns = len(all_turns)
        tp_total = fp_total = fn_total = 0
        slot_correct = slot_total = 0
        joint_correct = joint_total = 0
        bleu_scores = []
        diagnostics = {}

        # Conversation-level goal/task stats
        total_goals = len(self.conversations)
        completed_goals = 0
        total_tasks = len(self.conversations)
        successful_tasks = 0

        for conv_id, turns in self.conversations.items():
            if conv_id not in diagnostics:
                diagnostics[conv_id] = []

            # Determine if conversation completed a goal/task at least once
            conv_goal_completed = any(u.get("goal_completed") for u, _ in turns)
            conv_task_success = any(u.get("task_success") for u, _ in turns)
            if conv_goal_completed:
                completed_goals += 1
            if conv_task_success:
                successful_tasks += 1

            # Per-turn metrics
            for user_turn, system_turn in turns:
                gold_bs = user_turn.get("belief_state", {}) or {}
                pred_bs = system_turn.get("belief_state", {}) or {}

                # Inform metrics
                p, r, f1, tp, fp, fn = self._compute_inform_metrics_turn(gold_bs, pred_bs)
                tp_total += tp
                fp_total += fp
                fn_total += fn

                # Slot and joint accuracy
                corr_slots, total_slots = self._compute_slot_value_accuracy(gold_bs, pred_bs)
                slot_correct += corr_slots
                slot_total += total_slots
                j = self._compute_joint_goal_accuracy(gold_bs, pred_bs)
                joint_correct += j
                joint_total += 1

                # BLEU
                ref = user_turn.get("gold_system_response")  # fixed in your manual patch
                hyp = system_turn.get("system_response")
                bleu = self._compute_bleu(ref, hyp)
                bleu_scores.append(bleu)

                # Per-turn diagnostics
                diagnostics[conv_id].append({
                    "task_completed": user_turn.get("goal_completed"),
                    "dialog_turn": user_turn.get("dialog_turn"),
                    "user_utterance": user_turn.get("user_utterance"),
                    "system_response": system_turn.get("system_response"),
                    "reference_response": ref,
                    "gold_belief_state": gold_bs,
                    "pred_belief_state": pred_bs,
                    "inform_precision": p,
                    "inform_recall": r,
                    "inform_f1": f1,
                    "slot_value_accuracy": corr_slots / total_slots if total_slots > 0 else 0.0,
                    "joint_goal_accuracy": j,
                    "bleu": bleu
                })

        # Global metrics
        inform_precision = tp_total / (tp_total + fp_total + 1e-8) if (tp_total + fp_total) > 0 else 0.0
        inform_recall = tp_total / (tp_total + fn_total + 1e-8) if (tp_total + fn_total) > 0 else 0.0
        inform_f1 = (2 * inform_precision * inform_recall / (inform_precision + inform_recall + 1e-8)) \
            if (inform_precision + inform_recall) > 0 else 0.0

        slot_acc = slot_correct / slot_total if slot_total > 0 else 0.0
        joint_acc = joint_correct / joint_total if joint_total > 0 else 0.0
        avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0.0

        metrics = {
            "average_turns": total_turns,
            "goals_completed_rate": completed_goals / total_goals if total_goals > 0 else 0.0,
            "tasks_successful_rate": successful_tasks / total_tasks if total_tasks > 0 else 0.0,
            "inform_precision": inform_precision,
            "inform_recall": inform_recall,
            "inform_f1": inform_f1,
            "slot_value_accuracy": slot_acc,
            "joint_goal_accuracy": joint_acc,
            "bleu": avg_bleu
        }

        self.metrics = metrics
        self.diagnostics = diagnostics
        return metrics

    def get_metrics(self):
        self.compute_metrics()
        return self.metrics

    def get_diagnostics(self, conv_id: str = None):
        if conv_id:
            return self.diagnostics.get(conv_id, [])
        return self.diagnostics

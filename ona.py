import math
import time

next = 42

def myrand():
    global next
    next = next * 1103515245 + 12345
    return next//65536 % 32768

# Hyperparams
TRUTH_PROJECTION_DECAY = 0.8
TRUTH_EVIDENTIAL_HORIZON = 1.0
MAX_CONFIDENCE = 0.99
ANTICIPATION_CONFIDENCE = 0.0015
ANTICIPATION_THRESHOLD = 0.51  # 0.501
DECISION_THRESHOLD = 0.5  # 0.501
BABBLING_CHANCE = 1 # ten percent
BABBLE_DEACTIVATE_EXP = 0.51
GOAL_PQ_SIZE_MAX = 10  # PQ size
IMPLICATION_TABLE_SIZE_MAX = 30  # global implication table size
EVENT_FIFO_SIZE_MAX = 20

ops = ["^left", "^right"]
event_fifo = []
implication_table = []
goal_pq = []
current_time = 1.0


def truth_deduction(v1, v2):
    (_, c1), (f2, c2) = v1, v2
    f = f2*f2
    return (f, c1 * c2 * f)

def truth_deduction(v1, v2):
    """
    Perform truth deduction on two truth values.

    Args:
        v1 (tuple): The first truth value, a tuple of (frequency, confidence).
        v2 (tuple): The second truth value, a tuple of (frequency, confidence).

    Returns:
        tuple: The deduced truth value, a tuple of (frequency, confidence).
    """
    (_, c1), (f2, c2) = v1, v2
    f = f2 * f2
    return (f, c1 * c2 * f)

def truth_w2c(w):
    return w / (w + TRUTH_EVIDENTIAL_HORIZON)

def truth_induction(v2, v1):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f2, truth_w2c(f1 * c1 * c2))

def truth_intersection(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f1*f2, c1*c2)

def truth_projection(v, original_time, target_time):
    f, c = v
    difference = abs(target_time - original_time)
    return (f, c * (TRUTH_PROJECTION_DECAY ** difference))

def truth_eternalize(v):
    f, c = v
    return (f, truth_w2c(c))

def temporal_op_induction(antecedent_event, temporal_op, consequent_event):
    (term_a, time_a, truth_a) = antecedent_event
    (term_b, time_b, truth_b) = consequent_event
    (term_op, time_op, truth_op) = temporal_op
    
    # TODO include op in calculation
    truth_b_projected = truth_projection(truth_b, time_b, time_op)
    combined_truth = truth_intersection(truth_b_projected, truth_op)
    projected_to_a = truth_projection(combined_truth, time_op, time_a)
    final_truth = truth_eternalize(truth_induction(truth_a, projected_to_a))
    
    # (term_b, term_op, term_a) to distinguish (a => b) from (b => a)
    return ((term_b, term_op, term_a), final_truth)

def truth_c2w(c):
    return TRUTH_EVIDENTIAL_HORIZON * c / (1 - c)

def truth_expectation(v):
    f, c = v
    return (c * (f - 0.5) + 0.5)

def truth_revision(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    (w1, w2) = (truth_c2w(c1),  truth_c2w(c2))
    w = w1 + w2
    revised_f = min(1.0, (w1 * f1 + w2 * f2) / w)
    revised_c = min(MAX_CONFIDENCE, max(max(truth_w2c(w), c1), c2))
    return (revised_f, revised_c)

def implication_revision(imp1, imp2):
    ((term1, truth1), (term2, truth2)) = imp1, imp2
    if term1 != term2:
        raise ValueError("Implication terms do not match in implication_revision function")
    return (term1, truth_revision(truth1, truth2))

def anticipation():
    """
    Find all implications whose preconditions are fulfilled according to the implication table.
    """
    global implication_table
#    print("DEBUG")
#    print("Implication table: ")
#    print(implication_table)
    if len(event_fifo) < 2:
        return
    (termLast, occurrenceLast, truthLast) = event_fifo[-1]
    (termLastLast, occurrenceLastLast, truthLastLast) = event_fifo[-2]
    for i in range(len(implication_table)):
        currentImplication = implication_table[i]
#        print("DEBUG")
#        print("current implication: ")
#        print(currentImplication)
        ((precondition, op, consequence), (fImpl, cImpl)) = currentImplication
        isMatched = ((precondition == termLast and op is None) or  # <a =/> b>
                     (termLast in ops and op == termLast and precondition == termLastLast))  # <(a &/ ^op) =/> b>
        if fImpl > ANTICIPATION_THRESHOLD:
            revisedImplication = implication_revision(currentImplication, ((
                precondition, op, consequence), (0.0, ANTICIPATION_CONFIDENCE)))
        else:
            revisedImplication = currentImplication
        if isMatched:
            implication_table[i] = revisedImplication

def NAR_AddInputBelief(eventTerm, frequency=1.0, confidence=0.9, Volume=0):
    global event_fifo, implication_table, current_time
    event = (eventTerm, current_time, (frequency, confidence))
    print("Input:", str(event) + str(". :|:"))
    for i in range(1, len(event_fifo)):
        lastEvent = event_fifo[i]
        if lastEvent[0] in ops and event[0] not in ops and event_fifo[i-1][0] not in ops:
            newImplication = temporal_op_induction(
                event, lastEvent, event_fifo[i-1])
            ((pre, op, cons), (f, c)) = newImplication
            if c > 0 and Volume == 100:
                print("Derived: ", newImplication)
            T1 = (f, c)
            revised = False
            for i, (term2, _) in enumerate(implication_table):
                if (pre, op, cons) == term2:
                    implication_table[i] = implication_revision(
                        newImplication, implication_table[i])
                    revised = True
            if not revised:
                implication_table.append(newImplication)
                implication_table = implication_table[:IMPLICATION_TABLE_SIZE_MAX]
            implication_table.sort(key=lambda x: x[0])
    event_fifo.append(event)
    # remove first elements, since we appended event
    event_fifo = event_fifo[-EVENT_FIFO_SIZE_MAX:]
    current_time += 1
    anticipation()


def NAR_Cycle():  # decision making rule
    global goal_pq, current_time
#    print("DEBUG cycle position 1")
#    print("Goal PQ: ")
#    print(goal_pq)
    decision = (0.0, 0.0)
    if not goal_pq:
        current_time += 1
        return decision
    bestGoal = goal_pq[0]  # take out first element from goalPQ
    goal_pq = goal_pq[1:]  # with removal
    (_, (goalterm, occurrenceTime, desireGoal)) = bestGoal
    derivedGoals = []
    for i in range(len(implication_table)):
        ((precondition, operation, consequence),
         truthImpl) = implication_table[i]
        # pick the newest events with goalterm matching the preconditiong
        preconEvents = [x for x in event_fifo if x[0] == precondition]
        if len(preconEvents) == 0 or consequence != goalterm:  # if existent
            continue
        # by sorting according to occurrence time
        preconEvents.sort(key=lambda x: x[1])
        # and taking the last
        (preconTerm, preconOccurrence, truthPrecon) = preconEvents[-1]
        desirePrecondAndOp = truth_deduction(truthImpl, desireGoal)  # (a, op)!
        opDesireExp = truth_expectation(truth_deduction(
            desirePrecondAndOp, truth_projection(truthPrecon, preconOccurrence, current_time)))
        isBetterDecision = operation in ops and opDesireExp > decision[1]
        if isBetterDecision and opDesireExp > DECISION_THRESHOLD:
            decision = (operation, opDesireExp)
        desireSubgoal = truth_deduction(desirePrecondAndOp, (1.0, 0.9))
        derivedGoals.append((truth_expectation(desireSubgoal),
                            (precondition, current_time, desireSubgoal)))
    if decision[0] != 0.0:  # decision above threshold found?
        goal_pq = []
    else:
        goal_pq = goal_pq + derivedGoals
        goal_pq.sort(key=lambda x: x[0])  # again sort by desire exp
    if myrand() % BABBLING_CHANCE == 0 and decision[1] < BABBLE_DEACTIVATE_EXP:
        decision = (ops[myrand() % len(ops)], 1.0)
    if decision[0] != 0.0:  # a decision was made, add feedback event
        NAR_AddInputBelief(decision[0], 1.0, 0.9)
#    print("DEBUG cycle position 2")
#    print("Goal PQ: ")
#    print(goal_pq)
    current_time += 1
    return decision

def NAR_AddInputGoal(eventTerm, frequency=1.0, confidence=0.9, requires_grad=False):
    global goal_pq
#    print("DEBUG input goal position 1")
#    print("Goal PQ: ")
#    print(goal_pq)
    goal = (eventTerm, current_time, (frequency, confidence))
    print("Input:", str(goal) + "! :|:")
    goal_pq.append((truth_expectation((frequency, confidence)), goal))
    goal_pq = goal_pq[:GOAL_PQ_SIZE_MAX]
    goal_pq.sort(key=lambda x: x)
#    print("DEBUG input goal position 2")
#    print("Goal PQ: ")
#    print(goal_pq)
    return NAR_Cycle()


print("Operant conditioning example")

# NAR_AddInputBelief("A1")

# for k in range(1):
#     NAR_AddInputBelief("A1")
#     NAR_AddInputBelief("^left")
#     NAR_AddInputBelief("G")

#     for i in range(100):
#         NAR_Cycle()

#     NAR_AddInputBelief("A2")
#     NAR_AddInputBelief("^right")
#     NAR_AddInputBelief("G")
#     for i in range(100):
#         NAR_Cycle()

NAR_AddInputBelief("A2")
for i in range(1):
    NAR_Cycle()
# BABBLING_CHANCE = 1000000000000  # deactivate babbling
print(NAR_AddInputGoal("G"))
for i in range(1):
    NAR_Cycle()
NAR_AddInputBelief("G")
# NAR_AddInputGoal("G")

# ('^left', 0.5781976493957954) Expectation of the desire value

exit(0)
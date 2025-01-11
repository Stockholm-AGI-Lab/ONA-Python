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
eventFIFO = []
implicationTable = []
goalPQ = []
currentTime = 1.0


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

def temporal_op_induction(event1, operator, event2):
    (term1, occurrence_time1, truth1) = event1
    (term2, occurrence_time2, truth2) = event2
    (term_op, occurrence_time3, truth3) = operator
    # TODO include op in calculation
    truth2_to_op = truth_projection(truth2, occurrence_time2, occurrence_time3)
    truth23 = truth_intersection(truth2_to_op, truth3)
    truth23_to_1 = truth_projection(truth23, occurrence_time3, occurrence_time1)
    truth = truth_eternalize(truth_induction(truth1, truth23_to_1))
    # 2* to distinguish (a =/> b) from (b =/> a)
    return ((term2, term_op, term1), truth)

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
    global implicationTable
#    print("DEBUG")
#    print("Implication table: ")
#    print(implicationTable)
    if len(eventFIFO) < 2:
        return
    (termLast, occurrenceLast, truthLast) = eventFIFO[-1]
    (termLastLast, occurrenceLastLast, truthLastLast) = eventFIFO[-2]
    for i in range(len(implicationTable)):
        currentImplication = implicationTable[i]
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
            implicationTable[i] = revisedImplication

def NAR_AddInputBelief(eventTerm, frequency=1.0, confidence=0.9, Volume=0):
    global eventFIFO, implicationTable, currentTime
    event = (eventTerm, currentTime, (frequency, confidence))
    print("Input:", str(event) + str(". :|:"))
    for i in range(1, len(eventFIFO)):
        lastEvent = eventFIFO[i]
        if lastEvent[0] in ops and event[0] not in ops and eventFIFO[i-1][0] not in ops:
            newImplication = temporal_op_induction(
                event, lastEvent, eventFIFO[i-1])
            ((pre, op, cons), (f, c)) = newImplication
            if c > 0 and Volume == 100:
                print("Derived: ", newImplication)
            T1 = (f, c)
            revised = False
            for i, (term2, _) in enumerate(implicationTable):
                if (pre, op, cons) == term2:
                    implicationTable[i] = implication_revision(
                        newImplication, implicationTable[i])
                    revised = True
            if not revised:
                implicationTable.append(newImplication)
                implicationTable = implicationTable[:IMPLICATION_TABLE_SIZE_MAX]
            implicationTable.sort(key=lambda x: x[0])
    eventFIFO.append(event)
    # remove first elements, since we appended event
    eventFIFO = eventFIFO[-EVENT_FIFO_SIZE_MAX:]
    currentTime += 1
    anticipation()


def NAR_Cycle():  # decision making rule
    global goalPQ, currentTime
#    print("DEBUG cycle position 1")
#    print("Goal PQ: ")
#    print(goalPQ)
    decision = (0.0, 0.0)
    if not goalPQ:
        currentTime += 1
        return decision
    bestGoal = goalPQ[0]  # take out first element from goalPQ
    goalPQ = goalPQ[1:]  # with removal
    (_, (goalterm, occurrenceTime, desireGoal)) = bestGoal
    derivedGoals = []
    for i in range(len(implicationTable)):
        ((precondition, operation, consequence),
         truthImpl) = implicationTable[i]
        # pick the newest events with goalterm matching the preconditiong
        preconEvents = [x for x in eventFIFO if x[0] == precondition]
        if len(preconEvents) == 0 or consequence != goalterm:  # if existent
            continue
        # by sorting according to occurrence time
        preconEvents.sort(key=lambda x: x[1])
        # and taking the last
        (preconTerm, preconOccurrence, truthPrecon) = preconEvents[-1]
        desirePrecondAndOp = truth_deduction(truthImpl, desireGoal)  # (a, op)!
        opDesireExp = truth_expectation(truth_deduction(
            desirePrecondAndOp, truth_projection(truthPrecon, preconOccurrence, currentTime)))
        isBetterDecision = operation in ops and opDesireExp > decision[1]
        if isBetterDecision and opDesireExp > DECISION_THRESHOLD:
            decision = (operation, opDesireExp)
        desireSubgoal = truth_deduction(desirePrecondAndOp, (1.0, 0.9))
        derivedGoals.append((truth_expectation(desireSubgoal),
                            (precondition, currentTime, desireSubgoal)))
    if decision[0] != 0.0:  # decision above threshold found?
        goalPQ = []
    else:
        goalPQ = goalPQ + derivedGoals
        goalPQ.sort(key=lambda x: x[0])  # again sort by desire exp
    if myrand() % BABBLING_CHANCE == 0 and decision[1] < BABBLE_DEACTIVATE_EXP:
        decision = (ops[myrand() % len(ops)], 1.0)
    if decision[0] != 0.0:  # a decision was made, add feedback event
        NAR_AddInputBelief(decision[0], 1.0, 0.9)
#    print("DEBUG cycle position 2")
#    print("Goal PQ: ")
#    print(goalPQ)
    currentTime += 1
    return decision

def NAR_AddInputGoal(eventTerm, frequency=1.0, confidence=0.9, requires_grad=False):
    global goalPQ
#    print("DEBUG input goal position 1")
#    print("Goal PQ: ")
#    print(goalPQ)
    goal = (eventTerm, currentTime, (frequency, confidence))
    print("Input:", str(goal) + "! :|:")
    goalPQ.append((truth_expectation((frequency, confidence)), goal))
    goalPQ = goalPQ[:GOAL_PQ_SIZE_MAX]
    goalPQ.sort(key=lambda x: x)
#    print("DEBUG input goal position 2")
#    print("Goal PQ: ")
#    print(goalPQ)
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
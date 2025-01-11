import math
import time

next = 42

import random

def myrand():
    return random.randint(0, 32767)

# Constants (formerly hyperparameters)
TRUTH_PROJECTION_DECAY = 0.8
TRUTH_EVIDENTIAL_HORIZON = 1.0
MAX_CONFIDENCE = 0.99
ANTICIPATION_CONFIDENCE = 0.0015
ANTICIPATION_THRESHOLD = 0.51
DECISION_THRESHOLD = 0.5
BABBLING_CHANCE = 1
BABBLE_DEACTIVATE_EXP = 0.51
GOAL_PQ_SIZE_MAX = 10
IMPLICATION_TABLE_SIZE_MAX = 30
EVENT_FIFO_SIZE_MAX = 20

ops = ["^left", "^right", "^stop"]  # Operations

def initialize_state():
    return {
        "event_fifo": [],
        "implication_table": [],
        "goal_pq": [],
        "current_time": 1.0
    }

# Truth value operations
def truth_deduction(v1, v2):
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
    return (f1 * f2, c1 * c2)

def truth_projection(v, original_time, target_time):
    f, c = v
    difference = abs(target_time - original_time)
    return (f, c * (TRUTH_PROJECTION_DECAY ** difference))

def truth_eternalize(v):
    f, c = v
    return (f, truth_w2c(c))

def truth_c2w(c):
    return TRUTH_EVIDENTIAL_HORIZON * c / (1 - c)

def truth_expectation(v):
    f, c = v
    return c * (f - 0.5) + 0.5

def truth_revision(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    w1, w2 = truth_c2w(c1), truth_c2w(c2)
    w = w1 + w2
    revised_f = min(1.0, (w1 * f1 + w2 * f2) / w)
    revised_c = min(MAX_CONFIDENCE, max(max(truth_w2c(w), c1), c2))
    return (revised_f, revised_c)

def implication_revision(imp1, imp2):
    ((term1, truth1), (term2, truth2)) = imp1, imp2
    if term1 != term2:
        raise ValueError("Implication terms do not match in implication_revision function")
    return (term1, truth_revision(truth1, truth2))

# Core functions
def temporal_op_induction(state, antecedent_event, temporal_op, consequent_event):
    (term_a, time_a, truth_a) = antecedent_event
    (term_b, time_b, truth_b) = consequent_event
    (term_op, time_op, truth_op) = temporal_op

    truth_b_projected = truth_projection(truth_b, time_b, time_op)
    combined_truth = truth_intersection(truth_b_projected, truth_op)
    projected_to_a = truth_projection(combined_truth, time_op, time_a)
    final_truth = truth_eternalize(truth_induction(truth_a, projected_to_a))

    return ((term_b, term_op, term_a), final_truth)

def anticipation(state):
    if len(state["event_fifo"]) < 2:
        return state

    (term_last, occurrence_last, truth_last) = state["event_fifo"][-1]
    (term_last_last, occurrence_last_last, truth_last_last) = state["event_fifo"][-2]

    updated_table = state["implication_table"][:]
    for i in range(len(updated_table)):
        current_implication = updated_table[i]
        ((precondition, op, consequence), (f_impl, c_impl)) = current_implication

        is_matched = (
            (precondition == term_last and op is None) or
            (term_last in ops and op == term_last and precondition == term_last_last)
        )

        if is_matched:
            revised_implication = implication_revision(
                current_implication, ((precondition, op, consequence), (0.0, ANTICIPATION_CONFIDENCE))
            )
            updated_table[i] = revised_implication

    state["implication_table"] = updated_table
    return state

def NAR_AddInputBelief(state, event_term, frequency=1.0, confidence=0.9):
    event = (event_term, state["current_time"], (frequency, confidence))
    print("Input:", str(event) + ". :|:")

    updated_fifo = state["event_fifo"] + [event]
    updated_fifo = updated_fifo[-EVENT_FIFO_SIZE_MAX:]

    updated_implication_table = state["implication_table"][:]
    for i in range(1, len(updated_fifo)):
        last_event = updated_fifo[i]
        if last_event[0] in ops and event[0] not in ops and updated_fifo[i - 1][0] not in ops:
            new_implication = temporal_op_induction(state, event, last_event, updated_fifo[i - 1])
            revised = False

            for idx, (term2, _) in enumerate(updated_implication_table):
                if term2 == new_implication[0]:
                    updated_implication_table[idx] = implication_revision(new_implication, updated_implication_table[idx])
                    revised = True
                    break

            if not revised:
                updated_implication_table.append(new_implication)
                updated_implication_table = updated_implication_table[:IMPLICATION_TABLE_SIZE_MAX]

    updated_implication_table.sort(key=lambda x: x[0])
    state["event_fifo"] = updated_fifo
    state["implication_table"] = updated_implication_table
    state["current_time"] += 1

    return anticipation(state)

def NAR_Cycle(state):
    if not state["goal_pq"]:
        state["current_time"] += 1
        return (0.0, 0.0), state

    best_goal = state["goal_pq"].pop(0)
    _, (goal_term, occurrence_time, desire_goal) = best_goal

    derived_goals = []
    for ((precondition, operation, consequence), truth_impl) in state["implication_table"]:
        precon_events = [x for x in state["event_fifo"] if x[0] == precondition]

        if not precon_events or consequence != goal_term:
            continue

        precon_events.sort(key=lambda x: x[1])
        precon_term, precon_occurrence, truth_precon = precon_events[-1]

        desire_precond_and_op = truth_deduction(truth_impl, desire_goal)
        op_desire_exp = truth_expectation(
            truth_deduction(
                desire_precond_and_op,
                truth_projection(truth_precon, precon_occurrence, state["current_time"])
            )
        )

        if operation in ops and op_desire_exp > DECISION_THRESHOLD:
            decision = (operation, op_desire_exp)
        else:
            decision = (0.0, 0.0)

        desire_subgoal = truth_deduction(desire_precond_and_op, (1.0, 0.9))
        derived_goals.append((truth_expectation(desire_subgoal), (precondition, state["current_time"], desire_subgoal)))

    state["goal_pq"].extend(derived_goals)
    state["goal_pq"].sort(key=lambda x: x[0])

    if myrand() % BABBLING_CHANCE == 0:
        decision = (ops[myrand() % len(ops)], 1.0)

    if decision[0] != 0.0:
        state = NAR_AddInputBelief(state, decision[0], 1.0, 0.9)

    state["current_time"] += 1
    return decision, state

def NAR_AddInputGoal(state, event_term, frequency=1.0, confidence=0.9, requires_grad=False):
    goal = (event_term, state["current_time"], (frequency, confidence))
    print("Input:", str(goal) + "! :|:")

    state["goal_pq"].append((truth_expectation((frequency, confidence)), goal))
    state["goal_pq"] = state["goal_pq"][:GOAL_PQ_SIZE_MAX]
    state["goal_pq"].sort(key=lambda x: x)

    return NAR_Cycle(state)

# Example Usage
state = initialize_state()
#state = NAR_AddInputBelief(state, "A2")
#for _ in range(1):
#    _, state = NAR_Cycle(state)
#print(NAR_AddInputGoal(state, "G"))
#for i in range(1):
#    NAR_Cycle(state)
#NAR_AddInputBelief(state, "G")
#print(state)

def PrintBestProceduralHypothesis(state, pre, cons):
    for ((precondition, operation, consequence), (f, c)) in state["implication_table"]:
        if operation in ops and consequence == cons and precondition == pre:
            print(str(precondition) + " " + str(operation) + " " + str(consequence), "f=" + str(f), "c=" + str(c))
            return

NAR_Pong_Left_executed = False
NAR_Pong_Right_executed = False
NAR_Pong_Stop_executed = False

def Execute(decision):
    global NAR_Pong_Left_executed, NAR_Pong_Right_executed, NAR_Pong_Stop_executed
    op = decision[0]
    #print("OP!!!! " + str(op) + " " + str(decision[1]))
    if op == "^left":
        NAR_Pong_Left_executed = True
    elif op == "^right":
        NAR_Pong_Right_executed = True
    elif op == "^stop":
        NAR_Pong_Stop_executed = True

# PONG APPLICATION:
print(">>NAR Pong start")
szX = 50
szY = 20
ballX = int(szX/2)
ballY = int(szY/5)
batX = 20
batVX = 0
batWidth = 6  # "radius", batWidth from middle to the left and right
vX = 1
vY = 1
hits = 0
misses = 0
t = 0
iterations = -1
while True:
    if t > iterations and iterations != -1:
        break
    t += 1
    print("\033[1;1H\033[2J", end="")
    print("Hits=%d misses=%d ratio=%f time=%d\n" %
          (hits, misses, hits / (hits + misses) if hits + misses != 0 else 0, t))
    PrintBestProceduralHypothesis(state, "ball_right", "good_nar")
    PrintBestProceduralHypothesis(state, "ball_left", "good_nar")
    PrintBestProceduralHypothesis(state, "ball_equal", "good_nar")
    for i in range(int(batX-batWidth+1)):
        print(" ", end="")
    for i in range(int(batWidth*2-1+min(0, batX))):
        print("@", end="")
    print("")
    for i in range(ballY):
        for k in range(szX):
            print(" ", end="")
        print("|")
    for i in range(ballX):
        print(" ", end="")
    print("#", end="")
    for i in range(ballX+1, szX):
        print(" ", end="")
    print("|")
    for i in range(ballY+1, szY):
        for k in range(szX):
            print(" ", end="")
        print("|")
    if batX <= ballX - batWidth:
        print("RIGHT")
        state = NAR_AddInputBelief(state, "ball_right")
    elif ballX + batWidth < batX:
        print("LEFT")
        state = NAR_AddInputBelief(state, "ball_left")
    else:
        print("EQUAL")
        state = NAR_AddInputBelief(state, "ball_equal")
    Execute(NAR_AddInputGoal(state, "good_nar"))
    if ballX <= 0:
        vX = 1
    if ballX >= szX-1:
        vX = -1
    if ballY <= 0:
        vY = 1
    if ballY >= szY-1:
        vY = -1
    if t % 2 == -1:
        ballX = int(ballX + vX)
    ballY = int(ballY + vY)
    if ballY == 0:
        if abs(ballX-batX) <= batWidth:
            state = NAR_AddInputBelief(state, "good_nar")
            print("good")
            hits += 1
        else:
            print("bad")
            misses += 1
    if ballY == 0 or ballX == 0 or ballX >= szX-1:
        ballY = int(szY/2+myrand() % (szY/2))
        ballX = myrand() % szX
        vX = 1 if myrand() % 2 == 0 else -1
    if NAR_Pong_Left_executed:
        NAR_Pong_Left_executed = False
        print("Exec: op_left")
        batVX = -3
    if NAR_Pong_Right_executed:
        NAR_Pong_Right_executed = False
        print("Exec: op_right")
        batVX = 3
    if NAR_Pong_Stop_executed:
        NAR_Pong_Stop_executed = False
        print("Exec: op_stop")
        batVX = 0
    batX = max(-batWidth*2, min(szX-1+batWidth, batX+batVX*batWidth/2))
    batVX = 0
    if iterations == -1:
        time.sleep(0.01)
    # currentTime += 2
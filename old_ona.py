import math
import time

next = 42


def myrand():
    global next
    next = next * 1103515245 + 12345
    return next//65536 % 32768


# hyperparams
TRUTH_PROJECTION_DECAY = 0.8
TRUTH_EVIDENTAL_HORIZON = 1.0
MAX_CONFIDENCE = 0.99
ANTICIPATION_CONFIDENCE = 0.0015
ANTICIPATION_THRESHOLD = 0.51  # 0.501
DECISION_THRESHOLD = 0.5  # 0.501
BABBLING_CHANCE = 1 # ten percent
BABBLE_DEACTIVATE_EXP = 0.51
GOAL_PQ_SIZE_MAX = 10  # PQ size
IMPLICATION_TABLE_SIZE_MAX = 30  # global implication table size
EVENT_FIFO_SIZE_MAX = 20

ops = ["^left", "^right", "^stop"] 
eventFIFO = []
implicationTable = []
goalPQ = []
currentTime = 1.0


def Truth_Deduction(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    f = f2*f2
    return (f, c1 * c2 * f)


def Truth_w2c(w):
    return w / (w + TRUTH_EVIDENTAL_HORIZON)


def Truth_Induction(v2, v1):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f2, Truth_w2c(f1 * c1 * c2))


def Truth_Intersection(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    return (f1*f2, c1*c2)


def Truth_Projection(v, originalTime, targetTime):
    (f, c) = v
    difference = abs(targetTime - originalTime)
    return (f, c * math.pow(TRUTH_PROJECTION_DECAY, difference))


def Truth_Eternalize(v):
    (f, c) = v
    return (f, Truth_w2c(c))


def Temporal_OpInduction(event1, operator, event2):
    (term1, occurrenceTime1, truth1) = event1
    (term2, occurrenceTime2, truth2) = event2
    (termOp, occurrenceTime3, truth3) = operator
    # TODO include op in calculation
    truth2ToOp = Truth_Projection(truth2, occurrenceTime2, occurrenceTime3)
    truth23 = Truth_Intersection(truth2ToOp, truth3)
    truth23To1 = Truth_Projection(truth23, occurrenceTime3, occurrenceTime1)
    truth = Truth_Eternalize(Truth_Induction(truth1, truth23To1))
    # 2* to distinguish (a =/> b) from (b =/> a)
    return ((term2, termOp, term1), truth)


def Truth_c2w(c):
    return TRUTH_EVIDENTAL_HORIZON * c / (1 - c)


def Truth_Expectation(v):
    (f, c) = v
    return (c * (f - 0.5) + 0.5)


def Truth_Revision(v1, v2):
    ((f1, c1), (f2, c2)) = (v1, v2)
    (w1, w2) = (Truth_c2w(c1),  Truth_c2w(c2))
    w = w1 + w2
    return (min(1.0, (w1 * f1 + w2 * f2) / w), min(MAX_CONFIDENCE, max(max(Truth_w2c(w), c1), c2)))


def Implication_Revision(imp1, imp2):
    ((term1, truth1), (term2, truth2)) = (imp1, imp2)
    if term1 != term2:
        print("ERROR")
        exit(0)
    return (term1, Truth_Revision(truth1, truth2))


def Anticipation():  # find all implications which preconditions are fulfilled according to the implication table
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
            revisedImplication = Implication_Revision(currentImplication, ((
                precondition, op, consequence), (0.0, ANTICIPATION_CONFIDENCE)))
        else:
            revisedImplication = currentImplication
        if isMatched:
            implicationTable[i] = revisedImplication


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
        desirePrecondAndOp = Truth_Deduction(truthImpl, desireGoal)  # (a, op)!
        opDesireExp = Truth_Expectation(Truth_Deduction(
            desirePrecondAndOp, Truth_Projection(truthPrecon, preconOccurrence, currentTime)))
        isBetterDecision = operation in ops and opDesireExp > decision[1]
        if isBetterDecision and opDesireExp > DECISION_THRESHOLD:
            decision = (operation, opDesireExp)
        desireSubgoal = Truth_Deduction(desirePrecondAndOp, (1.0, 0.9))
        derivedGoals.append((Truth_Expectation(desireSubgoal),
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


def NAR_AddInputBelief(eventTerm, frequency=1.0, confidence=0.9, Volume=0):
    global eventFIFO, implicationTable, currentTime
    event = (eventTerm, currentTime, (frequency, confidence))
    print("Input:", str(event) + str(". :|:"))
    for i in range(1, len(eventFIFO)):
        lastEvent = eventFIFO[i]
        if lastEvent[0] in ops and event[0] not in ops and eventFIFO[i-1][0] not in ops:
            newImplication = Temporal_OpInduction(
                event, lastEvent, eventFIFO[i-1])
            ((pre, op, cons), (f, c)) = newImplication
            if c > 0 and Volume == 100:
                print("Derived: ", newImplication)
            T1 = (f, c)
            revised = False
            for i, (term2, _) in enumerate(implicationTable):
                if (pre, op, cons) == term2:
                    implicationTable[i] = Implication_Revision(
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
    Anticipation()


def NAR_AddInputGoal(eventTerm, frequency=1.0, confidence=0.9, requires_grad=False):
    global goalPQ
#    print("DEBUG input goal position 1")
#    print("Goal PQ: ")
#    print(goalPQ)
    goal = (eventTerm, currentTime, (frequency, confidence))
    print("Input:", str(goal) + "! :|:")
    goalPQ.append((Truth_Expectation((frequency, confidence)), goal))
    goalPQ = goalPQ[:GOAL_PQ_SIZE_MAX]
    goalPQ.sort(key=lambda x: x)
#    print("DEBUG input goal position 2")
#    print("Goal PQ: ")
#    print(goalPQ)
    return NAR_Cycle()

def PrintBestProceduralHypothesis(pre, cons):
    for ((precondition, operation, consequence), (f,c)) in implicationTable:
        if operation in ops and consequence == cons and precondition == pre:
            print(str(precondition) + " " + str(operation) + " " + str(consequence), "f="+str(f), "c="+str(c))
            return


NAR_Pong_Left_executed = False
NAR_Pong_Right_executed = False
NAR_Pong_Stop_executed = False

def Execute(decision):
    global NAR_Pong_Left_executed, NAR_Pong_Right_executed, NAR_Pong_Stop_executed
    op = decision[0]
    print("OP!!!! " + str(op) + " " + str(decision[1]))
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
    PrintBestProceduralHypothesis("ball_right", "good_nar")
    PrintBestProceduralHypothesis("ball_left", "good_nar")
    PrintBestProceduralHypothesis("ball_equal", "good_nar")
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
        NAR_AddInputBelief("ball_right")
    elif ballX + batWidth < batX:
        print("LEFT")
        NAR_AddInputBelief("ball_left")
    else:
        print("EQUAL")
        NAR_AddInputBelief("ball_equal")
    Execute(NAR_AddInputGoal("good_nar"))
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
            NAR_AddInputBelief("good_nar")
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

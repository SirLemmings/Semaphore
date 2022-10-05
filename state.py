class State:
    def __init__(self) -> None:
        self.bc_epochs = {}#{epoch: alias}
        self.taken_nyms = set()
        self.nym_owners = {}#{alias: nym}
        
    
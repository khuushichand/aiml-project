class _BaseModel:
    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        # Return a simple object instance; tests will patch this method
        return cls()


class EncDecRNNTBPEModel(_BaseModel):
    pass


class EncDecMultiTaskModel(_BaseModel):
    pass


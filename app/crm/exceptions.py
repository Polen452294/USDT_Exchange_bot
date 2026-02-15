class CRMError(Exception):
    pass


class CRMAuthError(CRMError):
    pass


class CRMTemporaryError(CRMError):
    pass


class CRMInvalidResponse(CRMError):
    pass
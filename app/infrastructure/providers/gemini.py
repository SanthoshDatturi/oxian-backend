from google.genai import errors as genai_errors


def is_gemini_dependency_error(exc: BaseException) -> bool:
    if isinstance(
        exc, (genai_errors.ServerError, genai_errors.UnknownApiResponseError)
    ):
        return True

    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        return isinstance(code, int) and (code >= 500 or code == 429)

    return False

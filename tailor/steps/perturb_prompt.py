from munch import Munch
from typing import Any, Dict, List, Optional, NamedTuple, Union
from tango.step import Step

# from tailor.steps.generate_prompts_by_tags import PromptObject
from tailor.steps.get_srl_tags import ProcessedSentence
from tailor.common.perturb_function import PerturbFunction, PerturbStringFunction
from tailor.common.perturbation_criteria import (
    PerturbationCriteria,
    AllVerbs,
    ArgsToBlankCondition,
    UniqueTags,
)

from tailor.common.latest_utils import (
    gen_prompts_by_tags,
    get_unique_prompts,
    gen_prompt_by_perturb_str,
    is_equal_headers,
    is_equal_prompts,
)

from tailor.common.perturbation_controls import validate_perturb_str

"""
TODO: General case, you deal with one field: ie. just premise in nli.
Sometimes you want something like: do something to question based on context in qa.
So, another type of step for such cases where you take 2 processed sentences, and
determine which one is A and B, respectively.
"""


class PromptObject(NamedTuple):
    """
    TODO
    """

    prompt: Optional[str] = None
    answer: Optional[str] = None
    meta: Optional[Munch] = None  # TODO: use a PromptMeta abstraction.


def _munch_to_prompt_object(prompt_munch: Munch):
    return PromptObject(
        prompt=prompt_munch.prompt, answer=prompt_munch.answer, meta=prompt_munch.meta
    )


def get_unique_prompt_objects(prompts: List[PromptObject]):
    """Helper function to get unique prompts given list of prompts
    Helpful when we care about a looser notion of equality than exact string equality
    Calls is_equal_prompts() to check equality of prompts
    """
    prompt_set: List[PromptObject] = []
    for p in prompts:
        if not any(is_equal_prompts(p.prompt, exist_p.prompt) for exist_p in prompt_set):
            prompt_set.append(p)
    return prompt_set


@Step.register("perturb-prompt-with-str")
class PerturbPromptWithFunction(Step):
    """
    TODO: Docs

    Note: When using config, FromParams will try to resolve `perturb_str_func`
    to a registered `PerturbStringFunction` class first. If it doesn't find a
    registered class, it will treat it as a perturb string and validate it,
    i.e., the string needs to contain at least one of CONTEXT, CORE, NONCORE, VERB wrappers.
    """

    DETERMINISTIC = True
    CACHEABLE = True

    def run(
        self,
        processed_sentences: List[ProcessedSentence],
        intermediate_prompt_kwargs: Dict[str, Any],
        perturb_str_func: Union[PerturbStringFunction, str],
        criteria_func: PerturbationCriteria = AllVerbs(),
        args_to_blank_condition: ArgsToBlankCondition = UniqueTags(),
    ) -> List[List[str]]:
        all_prompts = []
        for processed in processed_sentences:
            sentence_prompts = []
            for tags in criteria_func(processed):
                args_to_blank = args_to_blank_condition(tags)
                tags_prompt = gen_prompts_by_tags(
                    processed.spacy_doc,
                    frameset_id=None,
                    raw_tags=tags,
                    args_to_blank=args_to_blank,
                    return_prompt_type="concrete",
                    **intermediate_prompt_kwargs,
                )

                if isinstance(perturb_str_func, PerturbStringFunction):
                    perturb_str = perturb_str_func(tags_prompt.meta)
                    # TODO: return an object with metadata info: which perturb func created the prompt.

                else:
                    validate_perturb_str(perturb_str_func)
                    perturb_str = perturb_str_func

                perturbed = gen_prompt_by_perturb_str(
                    processed.spacy_doc, tags, perturb_str, tags_prompt.meta
                )

                if is_equal_headers(perturbed.prompt, tags_prompt.prompt):
                    prompt = None
                else:
                    prompt = _munch_to_prompt_object(perturbed)

                if prompt is not None:
                    sentence_prompts.append(prompt)
            sentence_prompts = get_unique_prompt_objects(sentence_prompts)
            all_prompts.append(sentence_prompts)
        return all_prompts


@Step.register("perturb-prompt-with-function")
class PerturbPrompt(Step):
    """
    TODO
    """

    DETERMINISTIC = True
    CACHEABLE = True

    def run(
        self,
        processed_sentences: List[ProcessedSentence],
        intermediate_prompt_kwargs: Dict[str, Any],
        perturb_fn: PerturbFunction,
        criteria_func: PerturbationCriteria = AllVerbs(),
        args_to_blank_condition: ArgsToBlankCondition = UniqueTags(),
        **perturb_fn_kwargs,
    ) -> List[List[str]]:
        all_prompts = []
        for processed in processed_sentences:
            sentence_prompts = []
            for tags in criteria_func(processed):
                args_to_blank = args_to_blank_condition(tags)
                tags_prompt = gen_prompts_by_tags(
                    processed.spacy_doc,
                    frameset_id=None,
                    raw_tags=tags,
                    args_to_blank=args_to_blank,
                    return_prompt_type="concrete",
                    **intermediate_prompt_kwargs,
                )

                prompt = perturb_fn(processed.spacy_doc, tags_prompt, tags)
                if prompt is not None:
                    sentence_prompts.append(prompt)
            sentence_prompts = get_unique_prompts(sentence_prompts)
            all_prompts.append(sentence_prompts)
        return all_prompts

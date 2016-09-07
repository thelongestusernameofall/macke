"""
Count partial error analysis and track the reasons, why MACKE did no finish
"""
from .helper import (
    get_error_registry_for_mackedir, get_klee_registry_from_mackedir,
    generic_main)
from ..CallGraph import CallGraph
from ..Klee import reconstruct_from_macke_dir
from collections import OrderedDict
from os import path


def partial(macke_directory):
    registry = get_error_registry_for_mackedir(macke_directory)
    cg = CallGraph(path.join(macke_directory, "bitcode", "program.bc"))
    klees = reconstruct_from_macke_dir(macke_directory)
    kinfos = get_klee_registry_from_mackedir(macke_directory)

    # Merge KLEEs and kinfos
    for klee in klees:
        kinfos[klee.get_outname()]["klee"] = klee

    # Generate index structure for easy access
    kphaseone = dict()  # function -> kleeResult
    kphasetwo = dict()  # caller,callee -> kleeResult
    for _, kinfo in kinfos.items():
        if kinfo["phase"] == 1:
            kphaseone[kinfo["function"]] = kinfo["klee"]
        elif kinfo["phase"] == 2:
            kphasetwo[(kinfo["caller"], kinfo["callee"])] = kinfo["klee"]

    # Sanitized  I: All leafs are only from phase one and have no errors
    sanatizedone = 0
    # Sanitized II: All leafs have no errors (phase one + two)
    sanatizedtwo = 0
    complete = 0
    kleecrash = 0
    noencapsulation = 0
    outofressources = 0
    targetmissed = 0
    incomplete = 0

    for vulninst, errorlist in registry.forvulninst.items():

        # Extract all erroneous functions and caller-callee pairs that is
        # (partial) covered by this error
        erroneous, callpairs = set(), set()
        for error in errorlist:
            erroneous.add(error.entryfunction)
            callpairs.update(
                {(caller, error.entryfunction)
                 for caller in cg[error.entryfunction]["calledby"]})

        border = {(cler, clee) for (cler, clee) in callpairs
                  if cler not in erroneous}

        if all(not kphaseone[cler].did_klee_run_out_of_ressources()
               for cler, _ in border):
            sanatizedone += 1
        elif all(
                not kphaseone[cler].did_klee_run_out_of_ressources() or (
                    not kphasetwo[
                        (cler, clee)].did_klee_run_out_of_ressources() and
                    kphasetwo[(cler, clee)].did_klee_reach_error_summary(clee)
                ) for cler, clee in border):
            sanatizedtwo += 1

        isincomplete = False

        if any(not (cg.is_symbolic_encapsulable(cler) or cler == "main")
               for cler, _ in border):
            noencapsulation += 1
            isincomplete = True

        if any(kphaseone[cler].did_klee_crash() or
               kphasetwo[(cler, clee)].did_klee_crash()
               for cler, clee in border):
            kleecrash += 1
            isincomplete = True

        if any(kphaseone[cler].did_klee_run_out_of_ressources() or
               kphasetwo[(cler, clee)].did_klee_run_out_of_ressources()
               for cler, clee in border):
            outofressources += 1
            isincomplete = True

        if any(not kphasetwo[(cler, clee)].did_klee_reach_error_summary(clee)
               for cler, clee in border):
            targetmissed += 1
            isincomplete = True

        incomplete += isincomplete
        complete += not isincomplete

    return OrderedDict([
        ("vulnerable-instructions", registry.count_vulnerable_instructions()),
        ("sanatized-one", sanatizedone),
        ("sanatized-two", sanatizedtwo),
        ("complete", complete),
        ("incomplete", incomplete),
        ("reasons", OrderedDict([
            ("kleecrash", kleecrash),
            ("noencapsulation", noencapsulation),
            ("out-of-resources", outofressources),
            ("target-missed", targetmissed)
        ]))
    ])


def main():
    generic_main(
        "Count partial error analysis and track the reasons for it",
        "The partial analysis were stored in %s",
        "partial.json", partial
    )

if __name__ == '__main__':
    main()

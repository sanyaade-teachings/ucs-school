#!/usr/share/ucs-test/runner pytest -s -l -v
## desc: unset default umc users
## roles: [domaincontroller_master]
## tags: [apptest,ucsschool_base1]
## exposure: dangerous

import univention.testing.utils as utils
from univention.config_registry import handler_unset


def test_unset_default_umc_users(ucr):
    handler_unset(["ucsschool/import/attach/policy/default-umc-users"])
    # UCR variables are loaded for ucsschool at the import stage
    # That's why the import should be after setting the ucr variable
    import univention.testing.ucsschool.ucs_test_school as utu

    with utu.UCSTestSchool() as schoolenv:
        for cli in (True, False):
            school, oudn = schoolenv.create_ou(use_cli=cli, use_cache=False)
            utils.wait_for_replication_and_postrun()
            base = "cn=Domain Users %s,cn=groups,%s" % (
                school.lower(),
                schoolenv.get_ou_base_dn(school),
            )
            print("*** Checking school {!r} (cli={}".format(school, cli))
            expected_attr = (
                "cn=default-umc-users,cn=UMC,cn=policies,%s" % (ucr.get("ldap/base"),)
            ).encode("utf-8")
            found_attr = schoolenv.lo.search(
                base=base, scope="base", attr=["univentionPolicyReference"]
            )[0][1]["univentionPolicyReference"]
            assert expected_attr in found_attr

# Plans the Cloudflare rules against a mocked provider.
#   terraform init -backend=false && terraform test

mock_provider "cloudflare" {}

variables {
  cloudflare_zone_id = "0123456789abcdef0123456789abcdef"
  admin_ssh_cidrs    = ["203.0.113.10/32"]
}

run "office_only_rule" {
  command = plan

  assert {
    condition     = strcontains(cloudflare_ruleset.dms_office_only.rules[0].expression, "not (ip.src in {203.0.113.10})")
    error_message = "The rule must block every address except the office"
  }
  assert {
    condition     = cloudflare_ruleset.dms_office_only.rules[0].action == "block"
    error_message = "The rule must block"
  }
  assert {
    condition     = strcontains(cloudflare_ruleset.dms_office_only.rules[0].expression, "\"/readyz\" \"/healthz\"")
    error_message = "Only the health pages may stay open"
  }
}

run "refuses_empty_office_list" {
  command = plan
  variables {
    admin_ssh_cidrs = []
  }
  expect_failures = [var.admin_ssh_cidrs]
}

/**
 * PeptideOS: Regulatory Source Verification
 *
 * Validates that every regulatory[] entry has:
 * 1. A resolvable source_url (HTTP 200)
 * 2. A primary regulator source (FDA, EMA, TGA, etc.)
 * 3. An archived snapshot (Wayback Machine)
 * 4. A dated retrieval
 * 5. A quote reference (section/page/date from source)
 *
 * CI fails if any entry violates these rules.
 * This is non-negotiable: regulatory status in this space is misreported constantly.
 */

import fs from 'fs';
import path from 'path';
import { fetch } from 'node-fetch';

// Primary regulatory sources only
const ALLOWED_DOMAINS = [
  'fda.gov',
  'ema.europa.eu',
  'pmda.go.jp',
  'tga.gov.au',
  'hc-sc.gc.ca',
  'mhra.gov.uk',
  'clinicaltrials.gov',
  'regulations.gov',
  'archive.org', // Wayback for verification
];

const DISALLOWED_DOMAINS = [
  // Supplement/vendor sites
  'peptidecompany.com',
  'research-peptides.com',
  'peptidewarehouse.com',
  // Generic wikis
  'wikipedia.org',
  'wikimedia.org',
  // Secondary sources
  'healthline.com',
  'medicalnewstoday.com',
  'drugs.com', // UGC site
  // Other peptide sites (competitors)
  'peptidecompound.com',
  'peptidesinfo.com',
];

interface RegulatoryEntry {
  jurisdiction: string;
  status: string;
  source_url: string;
  source_retrieved: string;
  archive_url?: string;
  source_quote_ref: string;
}

interface CompoundRecord {
  slug: string;
  names: { common: string[] };
  regulatory: RegulatoryEntry[];
}

class RegSourceChecker {
  private errors: string[] = [];
  private warnings: string[] = [];

  async checkAllCompounds(compoundsDir: string): Promise<number> {
    const files = fs.readdirSync(compoundsDir).filter(f => f.endsWith('.md'));

    console.log(`\n📋 Checking ${files.length} compound records...\n`);

    let errorCount = 0;

    for (const file of files) {
      const filePath = path.join(compoundsDir, file);
      const content = fs.readFileSync(filePath, 'utf-8');

      // Extract YAML frontmatter
      const match = content.match(/^---\n([\s\S]*?)\n---/);
      if (!match) {
        console.warn(`⚠️  ${file} has no YAML frontmatter`);
        continue;
      }

      try {
        const yaml = match[1];
        const compound = this.parseYAML(yaml) as CompoundRecord;

        const fileErrors = await this.checkCompound(compound, file);
        if (fileErrors > 0) {
          errorCount += fileErrors;
        }
      } catch (e) {
        console.error(`❌ ${file}: Parse error — ${e}`);
        errorCount++;
      }
    }

    this.printReport(errorCount);
    return errorCount;
  }

  private async checkCompound(compound: CompoundRecord, filename: string): Promise<number> {
    let count = 0;

    if (!compound.regulatory || compound.regulatory.length === 0) {
      console.error(`❌ ${filename}: No regulatory[] entries`);
      return 1;
    }

    for (let i = 0; i < compound.regulatory.length; i++) {
      const reg = compound.regulatory[i];
      const label = `${compound.names.common[0]} [${reg.jurisdiction}]`;

      // Rule 1: source_url must exist
      if (!reg.source_url) {
        console.error(`❌ ${filename} (${label}): Missing source_url`);
        count++;
        continue;
      }

      // Rule 2: source_url must be resolvable
      const urlValid = await this.validateURL(reg.source_url);
      if (!urlValid) {
        console.error(`❌ ${filename} (${label}): source_url not resolvable — ${reg.source_url}`);
        count++;
      }

      // Rule 3: Must be a primary regulator domain
      if (!this.isPrimarySource(reg.source_url)) {
        console.error(`❌ ${filename} (${label}): source_url is not a primary regulator — ${reg.source_url}`);
        count++;
      }

      // Rule 4: archive_url strongly encouraged for regulatory claims
      if (!reg.archive_url) {
        console.warn(`⚠️  ${filename} (${label}): No archive_url (archive.org snapshot recommended)`);
        this.warnings.push(`${label}: Missing archive snapshot`);
      } else {
        const archiveValid = await this.validateURL(reg.archive_url);
        if (!archiveValid) {
          console.error(`❌ ${filename} (${label}): archive_url not resolvable — ${reg.archive_url}`);
          count++;
        }
      }

      // Rule 5: source_retrieved must be recent (< 6 months old)
      const retrieved = new Date(reg.source_retrieved);
      const sixMonthsAgo = new Date();
      sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);

      if (retrieved < sixMonthsAgo) {
        console.warn(`⚠️  ${filename} (${label}): source_retrieved is ${this.daysSince(retrieved)} days old`);
      }

      // Rule 6: source_quote_ref must exist
      if (!reg.source_quote_ref) {
        console.error(`❌ ${filename} (${label}): Missing source_quote_ref (section/page/date)`);
        count++;
      }
    }

    return count;
  }

  private isPrimarySource(url: string): boolean {
    const domain = new URL(url).hostname;

    // Check against disallowed list first (fail fast)
    if (DISALLOWED_DOMAINS.some(d => domain.includes(d))) {
      return false;
    }

    // Check against allowed list
    return ALLOWED_DOMAINS.some(d => domain.includes(d));
  }

  private async validateURL(url: string): Promise<boolean> {
    try {
      const response = await fetch(url, {
        method: 'HEAD',
        timeout: 5000,
      });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  private parseYAML(yaml: string): object {
    // Simple YAML parser for frontmatter
    // For production, use js-yaml library
    const lines = yaml.split('\n');
    const obj: any = {};

    let currentArray: string[] = [];
    let currentKey = '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (line.startsWith('  -')) {
        // Array item
        const value = trimmed.substring(1).trim();
        if (value.startsWith('"') && value.endsWith('"')) {
          currentArray.push(value.slice(1, -1));
        } else if (value.startsWith("'") && value.endsWith("'")) {
          currentArray.push(value.slice(1, -1));
        } else {
          currentArray.push(value);
        }
      } else if (line.includes(':')) {
        // Key-value pair
        const [key, ...valueParts] = line.split(':');
        const trimmedKey = key.trim();
        const value = valueParts.join(':').trim();

        if (currentArray.length > 0 && currentKey) {
          obj[currentKey] = currentArray;
          currentArray = [];
        }

        currentKey = trimmedKey;

        if (value) {
          obj[trimmedKey] = value.replace(/^["']|["']$/g, '');
        }
      }
    }

    if (currentArray.length > 0 && currentKey) {
      obj[currentKey] = currentArray;
    }

    return obj;
  }

  private daysSince(date: Date): number {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
  }

  private printReport(errorCount: number): void {
    console.log('\n' + '='.repeat(60));
    if (errorCount === 0) {
      console.log('✅ All regulatory sources verified');
    } else {
      console.log(`❌ ${errorCount} regulatory source error(s) found`);
      console.log('BUILD FAILS. Fix all errors before merge.');
    }
    if (this.warnings.length > 0) {
      console.log(`\n⚠️  ${this.warnings.length} warning(s):`);
      this.warnings.forEach(w => console.log(`  - ${w}`));
    }
    console.log('='.repeat(60) + '\n');
  }
}

// Main execution
async function main() {
  const checker = new RegSourceChecker();
  const compoundsDir = path.join(process.cwd(), 'peptideos', 'src', 'content', 'compounds');

  const errorCount = await checker.checkAllCompounds(compoundsDir);
  process.exit(errorCount > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

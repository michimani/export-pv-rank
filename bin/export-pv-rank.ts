#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from '@aws-cdk/core';
import { ExportPvRankStack } from '../lib/export-pv-rank-stack';

const app = new cdk.App();
new ExportPvRankStack(app, 'ExportPvRankStack');
